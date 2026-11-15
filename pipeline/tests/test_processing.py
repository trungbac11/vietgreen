"""Offline contract tests for source formats and configuration."""
import io
import json
import tempfile
import unittest
from pathlib import Path

from pipeline.processing import MAX_BYTES, extract_document, fetch_source
from pipeline.run import load_sources


class FakeResponse(io.BytesIO):
    def __init__(self, body, headers=None):
        super().__init__(body)
        self.headers = headers or {}
    def geturl(self):
        return 'https://example.org/source'


class ProcessingTests(unittest.TestCase):
    def test_html_omits_scripts(self):
        pages, status = extract_document(b'<h1>Visible</h1><script>hidden()</script>', 'html')
        self.assertEqual(status, 'text_extracted')
        self.assertEqual(pages[0]['text'], 'Visible')

    def test_csv_and_json_are_parsed_without_metric_inference(self):
        pages, status = extract_document(b'name,value\nwater,5\n', 'csv')
        self.assertEqual(json.loads(pages[0]['text']), [{'name': 'water', 'value': '5'}])
        self.assertEqual(status, 'structured_extracted')
        pages, _ = extract_document(b'{"items":[1,2]}', 'json')
        self.assertEqual(json.loads(pages[0]['text'])['items'], [1, 2])

    def test_invalid_pdf_json_and_unknown_formats_fail(self):
        for payload, kind in [(b'not a pdf', 'pdf'), (b'{bad', 'json'), (b'x', 'zip')]:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                extract_document(payload, kind)

    def test_fetch_checks_scheme_and_content_length(self):
        with self.assertRaises(ValueError):
            fetch_source('file:///etc/passwd')
        with self.assertRaises(ValueError):
            fetch_source('https://example.org', lambda req, timeout: FakeResponse(b'x', {'Content-Length': str(MAX_BYTES + 1)}))
        body, content_type, url = fetch_source('https://example.org', lambda req, timeout: FakeResponse(b'ok', {'Content-Type': 'text/plain; charset=utf-8'}))
        self.assertEqual((body, content_type, url), (b'ok', 'text/plain', 'https://example.org/source'))

    def test_registry_rejects_duplicate_and_unsafe_ids(self):
        source = {'source_id':'bad/../id','company_id':'COM005','title':'t','url':'https://example.org','format':'pdf','source_type':'report'}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sources.json'
            path.write_text(json.dumps([source]))
            with self.assertRaises(ValueError): load_sources(path)
            source['source_id']='SRC001'
            path.write_text(json.dumps([source, source]))
            with self.assertRaises(ValueError): load_sources(path)

if __name__ == '__main__':
    unittest.main()
