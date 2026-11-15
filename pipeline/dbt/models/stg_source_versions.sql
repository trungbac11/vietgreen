-- A source version has already been captured and parsed; it is not a verified claim.
select version_id, source_id, company_id, source_url, title, source_type,
       content_sha256, object_key, content_type, fetched_at, page_count,
       extraction_status, review_status
from pipeline.source_versions
