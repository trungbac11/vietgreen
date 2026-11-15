-- Additive, rerunnable migration. No legacy fact or dimension rows are changed.
CREATE SCHEMA IF NOT EXISTS pipeline;
CREATE TABLE IF NOT EXISTS pipeline.ingestion_runs (
  run_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ, status TEXT NOT NULL,
  error_summary TEXT
);
CREATE TABLE IF NOT EXISTS pipeline.source_versions (
  version_id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES public.dim_source(source_id),
  company_id TEXT NOT NULL REFERENCES public.dim_company(company_id), source_url TEXT NOT NULL,
  title TEXT NOT NULL, source_type TEXT NOT NULL, content_sha256 TEXT NOT NULL,
  object_key TEXT NOT NULL, content_type TEXT NOT NULL, fetched_at TIMESTAMPTZ NOT NULL,
  page_count INTEGER NOT NULL CHECK (page_count > 0), extraction_status TEXT NOT NULL,
  review_status TEXT NOT NULL, UNIQUE (source_id, content_sha256)
);
CREATE TABLE IF NOT EXISTS pipeline.source_pages (
  version_id TEXT NOT NULL REFERENCES pipeline.source_versions(version_id),
  page_number INTEGER NOT NULL CHECK (page_number > 0), extracted_text TEXT NOT NULL,
  extracted_tables JSONB NOT NULL, PRIMARY KEY (version_id, page_number)
);
CREATE TABLE IF NOT EXISTS pipeline.acquisitions (
  run_id TEXT PRIMARY KEY REFERENCES pipeline.ingestion_runs(run_id),
  version_id TEXT NOT NULL REFERENCES pipeline.source_versions(version_id),
  observed_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS public.pipeline_document_evidence (
  source_id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES pipeline.source_versions(version_id),
  company_id TEXT NOT NULL REFERENCES public.dim_company(company_id), source_url TEXT NOT NULL,
  title TEXT NOT NULL, source_type TEXT NOT NULL, content_sha256 TEXT NOT NULL,
  object_key TEXT NOT NULL, content_type TEXT NOT NULL, fetched_at TIMESTAMPTZ NOT NULL,
  page_count INTEGER NOT NULL, extraction_status TEXT NOT NULL, review_status TEXT NOT NULL,
  published_at TIMESTAMPTZ NOT NULL
);
