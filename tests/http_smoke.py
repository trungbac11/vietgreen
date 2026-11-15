"""HTTP contract checks; BASE_URL selects the isolated instance to test."""
import csv
import io
import json
import os
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

BASE = os.getenv('BASE_URL', 'http://localhost:8000')


def get(path):
    with urlopen(BASE + path, timeout=10) as response:
        return response.status, response.read()


class HttpTests(unittest.TestCase):
    def test_health_and_catalog(self):
        status, raw = get('/api/health')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['database'], 'postgresql')
        _, raw = get('/api/catalog')
        catalog = json.loads(raw)
        self.assertEqual(catalog['summary']['observations'], 2046)
        self.assertTrue(any(d['source_id'] == 'SRC001' for d in catalog['pipeline_documents']))

    def test_pagination_and_year_filter(self):
        rows=[]
        for page in (1, 2):
            _, raw=get('/api/metrics?company_id=COM005&year=2024&limit=5&page='+str(page))
            payload=json.loads(raw)
            self.assertEqual(len(payload['rows']),5)
            self.assertTrue(all(r['company_id']=='COM005' and r['year']==2024 for r in payload['rows']))
            rows.append({r['observation_id'] for r in payload['rows']})
        self.assertFalse(rows[0] & rows[1])

    def test_export_and_error_responses(self):
        _, raw=get('/api/export?table=dim_company')
        self.assertEqual(len(list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))),6)
        for path, code in [('/api/metrics?page=bad',400),('/api/export?table=does_not_exist',400),('/api/not-a-route',404)]:
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                get(path)
            self.assertEqual(error.exception.code,code)

if __name__ == '__main__':
    unittest.main(verbosity=2)
