"""Run: python3 test_smoke.py (stdlib; SQLite preview, no Docker required)."""
import csv, os, sys, tempfile, unittest, shutil, sqlite3
from contextlib import closing
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'app'))
import db, server
class Smoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        os.environ.pop('DATABASE_URL',None)
        os.environ['SQLITE_PATH']=str(Path(cls.temp.name)/'test.db')
        # Simulate a database made by the earlier version of the demo.
        with closing(sqlite3.connect(os.environ['SQLITE_PATH'])) as old, old:
            old.execute('CREATE TABLE dim_company (company_id TEXT PRIMARY KEY, company_name TEXT, industry_id TEXT, is_food_company TEXT)')
        cls.rows=db.import_data()
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_existing_database_migrates_image_columns(self):
        with closing(db.connect()) as conn:
            company={r[1] for r in conn.execute('PRAGMA table_info(dim_company)').fetchall()}
            product={r[1] for r in conn.execute('PRAGMA table_info(dim_product)').fetchall()}
        self.assertIn('logo_path',company);self.assertIn('image_path',product)
    def test_counts_and_idempotent_import(self):
        self.assertEqual(db.import_data(),self.rows)
        catalog=server.catalog()
        self.assertEqual(len(catalog['dim_company']),6)
        self.assertEqual(len(catalog['dim_product']),30)
        self.assertEqual(catalog['summary']['observations'],2046)
        self.assertEqual(sum(row['observations'] for row in catalog['company_categories']),2046)
        self.assertEqual(sum(row['missing_values'] for row in catalog['company_categories']),150)
    def test_metric_filters_and_pagination(self):
        a=server.metrics({'company_id':['COM005'],'limit':['25']})
        b=server.metrics({'company_id':['COM005'],'limit':['25'],'page':['2']})
        self.assertEqual(len(a['rows']),25)
        self.assertFalse({x['observation_id'] for x in a['rows']} & {x['observation_id'] for x in b['rows']})
        y=server.metrics({'company_id':['COM005'],'year':['2024'],'limit':['500']})
        self.assertTrue(y['rows'])
        self.assertTrue(all(x['year']==2024 and x['company_id']=='COM005' for x in y['rows']))
    def test_series_and_image_paths(self):
        ms=server.query('SELECT DISTINCT f.metric_id FROM fact_environment_metric f WHERE f.company_id=? LIMIT 1',('COM005',))
        self.assertTrue(server.series({'company_id':['COM005'],'metric_id':[ms[0]['metric_id']]}))
        self.assertTrue(Path(ROOT/'app/static/images/logos/COM001.png').exists())
        self.assertTrue(Path(ROOT/'data/dim_company.csv').read_text().splitlines()[0].endswith('logo_path'))
        self.assertTrue(Path(ROOT/'data/dim_product.csv').read_text().splitlines()[0].endswith('image_path'))
    def test_bad_reference_prevents_partial_import(self):
        original=db.DATA;copy=Path(self.temp.name)/'bad';shutil.copytree(original,copy)
        file=copy/'dim_product.csv'
        with file.open(encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f);cols=reader.fieldnames;rows=list(reader)
        rows[0]['company_id']='DOES_NOT_EXIST'
        with file.open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader();writer.writerows(rows)
        db.DATA=copy
        try:
            with self.assertRaises(ValueError):db.import_data()
        finally:db.DATA=original
        self.assertEqual(db.query('SELECT COUNT(*) AS n FROM dim_product')[0]['n'],30)
    def test_cross_company_relationships_prevent_import(self):
        original=db.DATA
        for table,field in [('dim_product','brand_id'),('fact_environment_metric','report_id')]:
            with self.subTest(table=table):
                copy=Path(self.temp.name)/('mismatch_'+table);shutil.copytree(original,copy)
                file=copy/(table+'.csv')
                with file.open(encoding='utf-8-sig',newline='') as f:
                    reader=csv.DictReader(f);cols=reader.fieldnames;rows=list(reader)
                target='dim_brand' if field=='brand_id' else 'dim_report'
                with (copy/(target+'.csv')).open(encoding='utf-8-sig',newline='') as f:
                    options=list(csv.DictReader(f))
                rows[0][field]=next(r[field] for r in options if r['company_id'] and r['company_id']!=rows[0]['company_id'])
                with file.open('w',encoding='utf-8',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader();writer.writerows(rows)
                db.DATA=copy
                try:
                    with self.assertRaisesRegex(ValueError,'different companies'):db.import_data()
                finally:db.DATA=original
        self.assertEqual(db.query('SELECT COUNT(*) AS n FROM dim_product')[0]['n'],30)
if __name__=='__main__':unittest.main(verbosity=2)
