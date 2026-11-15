-- Published runs plus this run only: a failed/crashed run cannot leak into a later publish.
with ranked as (
  select v.*, a.observed_at,
    row_number() over (partition by v.source_id order by a.observed_at desc, a.run_id desc) as rn
  from {{ ref('stg_source_versions') }} v
  join pipeline.acquisitions a on a.version_id = v.version_id
  join pipeline.ingestion_runs r on r.run_id = a.run_id
  where r.status = 'success'
     or (r.run_id = '{{ var("run_id", "") }}' and r.status = 'running')
)
select version_id, source_id, company_id, source_url, title, source_type,
       content_sha256, object_key, content_type, observed_at as fetched_at, page_count,
       extraction_status, review_status
from ranked where rn = 1
