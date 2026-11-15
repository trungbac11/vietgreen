"""Destructive synthetic injection for an explicitly isolated test stack only."""
import os
from unittest.mock import patch
import psycopg
from pipeline import run

if os.environ.get('VIETGREEN_ISOLATED_TEST') != '1':
    raise SystemExit('Refusing to run without VIETGREEN_ISOLATED_TEST=1')

connect = lambda **kw: psycopg.connect(os.environ['DATABASE_URL'], **kw)
source = run.load_sources()[0]
client = run.storage_client()
bucket = os.environ.get('MINIO_BUCKET', 'vietgreen-raw')
with connect() as conn:
    before = conn.execute('SELECT version_id, content_sha256 FROM public.pipeline_document_evidence WHERE source_id=%s', (source['source_id'],)).fetchone()
    key = conn.execute('SELECT object_key FROM public.pipeline_document_evidence WHERE source_id=%s', (source['source_id'],)).fetchone()[0]
response = client.get_object(bucket, key)
try:
    body = response.read() + b'\n% synthetic test-only changed source\n'
finally:
    response.close()
    response.release_conn()
try:
    with patch('pipeline.run.fetch_source', return_value=(body, 'application/pdf', source['url'])), \
         patch('pipeline.run.run_dbt', side_effect=RuntimeError('injected test failure')):
        run.ingest(source, client, bucket, connect)
except RuntimeError as exc:
    assert str(exc) == 'injected test failure'
else:
    raise AssertionError('Injected error was not propagated')
with connect() as conn:
    after = conn.execute('SELECT version_id, content_sha256 FROM public.pipeline_document_evidence WHERE source_id=%s', (source['source_id'],)).fetchone()
    failed = conn.execute("SELECT count(*) FROM pipeline.ingestion_runs WHERE status='failed' AND error_summary='injected test failure'").fetchone()[0]
assert before == after, 'Published evidence changed after failed validation'
assert failed >= 1, 'Failure was not logged'
print('PASS injected failure logged; published version and checksum remain unchanged')
