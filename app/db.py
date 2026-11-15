import csv, os, re, sqlite3, math
from contextlib import closing
from pathlib import Path
DATA = Path(os.getenv('DATA_DIR', str(Path(__file__).resolve().parents[1] / 'data')))
PK = {'dim_company':'company_id','dim_industry':'industry_id','dim_product':'product_id','dim_brand':'brand_id','dim_product_category':'product_category_id','dim_metric':'metric_id','dim_unit':'unit_id','dim_report':'report_id','dim_source':'source_id','dim_certification':'certification_id','dim_award':'award_id','fact_environment_metric':'observation_id','fact_product_verification':'product_verification_id','fact_product_sustainability_claim':'claim_id','bridge_product_source':'product_source_id','bridge_product_certification':'product_certification_id','bridge_product_award':'product_award_id'}
ORDER = ['dim_industry','dim_company','dim_brand','dim_product_category','dim_product','dim_unit','dim_metric','dim_report','dim_source','dim_certification','dim_award','fact_environment_metric','fact_product_verification','fact_product_sustainability_claim','bridge_product_source','bridge_product_certification','bridge_product_award']
REF = {v:k for k,v in PK.items() if k.startswith('dim_')}
# default_unit_id is a declared reference too, added after both dimensions load.
def connect():
    if os.getenv('DATABASE_URL'):
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(os.environ['DATABASE_URL'],row_factory=dict_row)
    c=sqlite3.connect(os.getenv('SQLITE_PATH','/tmp/vietgreen-preview.db'))
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def query(sql,params=()):
    with closing(connect()) as c:
        cur=c.execute(sql.replace('?','%s') if os.getenv('DATABASE_URL') else sql,params)
        return [dict(r) for r in cur.fetchall()]

def load_files():
    tables={}
    for name in ORDER:
        with (DATA/(name+'.csv')).open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f); cols=reader.fieldnames
            if not cols or any(not re.fullmatch('[a-z][a-z0-9_]*',v) for v in cols):raise ValueError('Invalid CSV header: '+name)
            rows=list(reader)
        key=PK[name]
        ids=[r[key] for r in rows]
        if len(set(ids))!=len(ids) or '' in ids:raise ValueError('Duplicate/empty primary key: '+name)
        tables[name]=(cols,rows)
    for name,(cols,rows) in tables.items():
        for col in cols:
            target=REF.get('unit_id' if col=='default_unit_id' else col)
            if target and target!=name:
                valid={r[PK[target]] for r in tables[target][1]}
                bad=[r[col] for r in rows if r[col] and r[col] not in valid]
                if bad:raise ValueError(f'Orphan reference {name}.{col}: {bad[:3]}')
    # Valid FKs do not guarantee that related records belong to the same company.
    brands={row['brand_id']:row for row in tables['dim_brand'][1]}
    reports={row['report_id']:row for row in tables['dim_report'][1]}
    for row in tables['dim_product'][1]:
        brand=brands.get(row['brand_id'])
        if brand and row['company_id'] and brand['company_id'] and row['company_id']!=brand['company_id']:
            raise ValueError('Product and brand belong to different companies: '+row['product_id'])
    for row in tables['fact_environment_metric'][1]:
        report=reports.get(row['report_id'])
        if report and row['company_id'] and report['company_id'] and row['company_id']!=report['company_id']:
            raise ValueError('Observation and report belong to different companies: '+row['observation_id'])
    return tables

def col_type(name,col):
    if name=='fact_environment_metric' and col in ('value','source_value'):return 'DOUBLE PRECISION'
    if col in ('year','report_year','item_order','source_count','name_variant_count','unit_variant_count'):return 'INTEGER'
    return 'TEXT'

def import_data():
    tables=load_files(); pg=bool(os.getenv('DATABASE_URL'))
    with closing(connect()) as c, c:
        for name in ORDER:
            cols,rows=tables[name]
            defs=[]
            for col in cols:
                d=f'"{col}" {col_type(name,col)}'
                if col==PK[name]:d+=' PRIMARY KEY'
                target=REF.get('unit_id' if col=='default_unit_id' else col)
                if target and target!=name and target in ORDER[:ORDER.index(name)]:d+=f' REFERENCES "{target}"("{PK[target]}")'
                defs.append(d)
            c.execute(f'CREATE TABLE IF NOT EXISTS "{name}" ({", ".join(defs)})')
            if name in ('dim_company','dim_product'):
                image_col='logo_path' if name=='dim_company' else 'image_path'
                if pg:
                    c.execute(f'ALTER TABLE "{name}" ADD COLUMN IF NOT EXISTS "{image_col}" TEXT')
                else:
                    present={row[1] for row in c.execute(f'PRAGMA table_info("{name}")').fetchall()}
                    if image_col not in present:c.execute(f'ALTER TABLE "{name}" ADD COLUMN "{image_col}" TEXT')
            fields=','.join('"'+v+'"' for v in cols)
            placeholders=','.join(['%s' if pg else '?']*len(cols))
            updates=','.join(f'"{v}"=excluded."{v}"' for v in cols if v!=PK[name])
            sql=f'INSERT INTO "{name}" ({fields}) VALUES ({placeholders}) ON CONFLICT ("{PK[name]}") DO UPDATE SET {updates}'
            values=[]
            for row in rows:
                value=[]
                for col in cols:
                    v=row[col] or None
                    if v is not None and col_type(name,col)=='INTEGER':v=int(v)
                    if v is not None and col_type(name,col)=='DOUBLE PRECISION':
                        v=float(v)
                        if not math.isfinite(v):raise ValueError(f'Non-finite value in {name}.{col}')
                    value.append(v)
                values.append(value)
            with_cursor=c.cursor();with_cursor.executemany(sql,values)
        for table,col in [('fact_environment_metric','company_id'),('fact_environment_metric','metric_id'),('fact_environment_metric','year'),('dim_product','company_id')]:
            c.execute(f'CREATE INDEX IF NOT EXISTS idx_{table}_{col} ON {table} ({col})')
        c.execute('CREATE TABLE IF NOT EXISTS import_history (loaded_at TEXT, row_count INTEGER)')
        from datetime import datetime,timezone
        sql='INSERT INTO import_history VALUES (?,?)'
        c.execute(sql.replace('?','%s') if pg else sql,(datetime.now(timezone.utc).isoformat(),sum(len(x[1]) for x in tables.values())))
        c.commit()
    return {name:len(rows) for name,(cols,rows) in tables.items()}

def initialize():
    try:ready=bool(query('SELECT company_id FROM dim_company LIMIT 1'))
    except Exception:ready=False
    if not ready:import_data()

if __name__=='__main__':print(import_data())
