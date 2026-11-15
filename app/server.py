import json, os, csv, io, traceback
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from pathlib import Path
from db import initialize, query, ORDER, PK
from insights import trend_insights
STATIC=Path(__file__).parent/'static'

def pipeline_documents():
    """Return published evidence only; the optional pipeline may not be installed."""
    if os.getenv('DATABASE_URL'):
        exists=query("SELECT to_regclass('public.pipeline_document_evidence') AS name")[0]['name']
    else:
        exists=query("SELECT name FROM sqlite_master WHERE type='table' AND name='pipeline_document_evidence'")
    if not exists:
        return []
    return query("""SELECT d.source_id, d.version_id, d.company_id, d.source_url, d.title,
        d.source_type, d.content_sha256, CAST(d.fetched_at AS TEXT) AS fetched_at,
        CAST(d.published_at AS TEXT) AS published_at, d.page_count, d.extraction_status,
        d.review_status, SUBSTR(p.extracted_text, 1, 600) AS first_page_excerpt
        FROM pipeline_document_evidence d
        LEFT JOIN pipeline.source_pages p ON p.version_id=d.version_id AND p.page_number=1
        ORDER BY d.fetched_at DESC, d.source_id""")

def catalog():
    result={name:query('SELECT * FROM '+name) for name in ORDER if name!='fact_environment_metric'}
    result['summary']=query('SELECT COUNT(*) AS observations, MIN(year) AS first_year, MAX(year) AS last_year FROM fact_environment_metric')[0]
    result['years']=query('SELECT year, COUNT(*) AS count FROM fact_environment_metric GROUP BY year ORDER BY year')
    result['company_stats']=query('SELECT company_id, COUNT(*) AS observations, COUNT(DISTINCT metric_id) AS metrics, MIN(year) AS first_year, MAX(year) AS last_year FROM fact_environment_metric GROUP BY company_id')
    result['company_categories']=query("""SELECT f.company_id, COALESCE(m.category, 'Not classified') AS category,
        COUNT(*) AS observations, SUM(CASE WHEN f.value IS NULL THEN 1 ELSE 0 END) AS missing_values
        FROM fact_environment_metric f LEFT JOIN dim_metric m ON m.metric_id=f.metric_id
        GROUP BY f.company_id, COALESCE(m.category, 'Not classified') ORDER BY f.company_id, observations DESC""")
    result['quality']=query("SELECT review_status, COUNT(*) AS count FROM fact_environment_metric GROUP BY review_status")
    result['measurement_types']=query("SELECT measurement_type, COUNT(*) AS count FROM fact_environment_metric GROUP BY measurement_type ORDER BY count DESC")
    result['imports']=query('SELECT * FROM import_history ORDER BY loaded_at DESC LIMIT 1')
    result['pipeline_documents']=pipeline_documents()
    return result

def metrics(params):
    where=[];args=[]
    for field in ['company_id','metric_id','unit_id','year','entity','boundary','measurement_type']:
        if params.get(field):where.append('f.'+field+' = ?');args.append(params[field][0])
    if params.get('q'):
        where.append('(LOWER(m.metric_name_vi) LIKE ? OR LOWER(f.source_metric_name_vi) LIKE ?)')
        args += ['%'+params['q'][0].lower()+'%']*2
    clause=' WHERE '+' AND '.join(where) if where else ''
    page=max(1,int(params.get('page',['1'])[0]));limit=min(500,max(1,int(params.get('limit',['25'])[0])))
    joins=' FROM fact_environment_metric f LEFT JOIN dim_metric m ON m.metric_id=f.metric_id LEFT JOIN dim_unit u ON u.unit_id=f.unit_id LEFT JOIN dim_company c ON c.company_id=f.company_id LEFT JOIN dim_report r ON r.report_id=f.report_id'
    count=query('SELECT COUNT(*) AS n'+joins+clause,args)[0]['n']
    rows=query('SELECT f.*, m.metric_name_vi, m.category, u.unit_code, c.company_name, r.source_file, r.report_type, r.report_year'+joins+clause+' ORDER BY f.year DESC, f.observation_id LIMIT ? OFFSET ?',args+[limit,(page-1)*limit])
    return dict(rows=rows,total=count,page=page,limit=limit)

def series(params):
    if not params.get('company_id') or not params.get('metric_id'):return []
    return query('SELECT f.*, u.unit_code, r.report_type, r.source_file FROM fact_environment_metric f LEFT JOIN dim_unit u ON u.unit_id=f.unit_id LEFT JOIN dim_report r ON r.report_id=f.report_id WHERE f.company_id=? AND f.metric_id=? ORDER BY f.year,f.observation_id',(params['company_id'][0],params['metric_id'][0]))

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(STATIC),**kwargs)
    def send_json(self,data,status=200):
        b=json.dumps(data,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        url=urlparse(self.path);params=parse_qs(url.query)
        try:
            if url.path=='/api/health':self.send_json({'status':'ok','database':'postgresql' if os.getenv('DATABASE_URL') else 'sqlite-preview','companies':query('SELECT COUNT(*) AS n FROM dim_company')[0]['n']})
            elif url.path=='/api/catalog':self.send_json(catalog())
            elif url.path=='/api/metrics':self.send_json(metrics(params))
            elif url.path=='/api/insights':
                rows=query('SELECT f.*, m.metric_name_vi, u.unit_code, r.source_file FROM fact_environment_metric f LEFT JOIN dim_metric m ON m.metric_id=f.metric_id LEFT JOIN dim_unit u ON u.unit_id=f.unit_id LEFT JOIN dim_report r ON r.report_id=f.report_id')
                result=trend_insights(rows)
                if params.get('company_id'):result=[x for x in result if x['company_id']==params['company_id'][0]]
                self.send_json(result)
            elif url.path=='/api/company-metrics':self.send_json(query('SELECT DISTINCT f.metric_id, m.metric_name_vi FROM fact_environment_metric f JOIN dim_metric m ON m.metric_id=f.metric_id WHERE f.company_id=? ORDER BY m.metric_name_vi',(params.get('company_id',[''])[0],)))
            elif url.path=='/api/series':self.send_json(series(params))
            elif url.path=='/api/export':
                table=params.get('table',['dim_company'])[0]
                if table not in ORDER:self.send_json({'error':'Unknown table'},400);return
                rows=query('SELECT * FROM '+table);buff=io.StringIO();buff.write('\ufeff')
                if rows:
                    w=csv.DictWriter(buff,fieldnames=rows[0]);w.writeheader()
                    for r in rows:
                        # Excel formula injection mitigation; original database remains unchanged.
                        w.writerow({k:"'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v for k,v in r.items()})
                b=buff.getvalue().encode();self.send_response(200);self.send_header('Content-Type','text/csv; charset=utf-8');self.send_header('Content-Disposition',f'attachment; filename="{table}.csv"');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
            elif url.path.startswith('/api/'):self.send_json({'error':'Not found'},404)
            else:super().do_GET()
        except ValueError:self.send_json({'error':'Invalid filter or page'},400)
        except Exception:
            traceback.print_exc();self.send_json({'error':'Database request failed; inspect application logs'},500)

if __name__=='__main__':
    initialize();port=int(os.getenv('PORT','8000'));print(f'VietGreen ready on port {port}',flush=True)
    ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
