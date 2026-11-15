with page_counts as (
  select version_id, count(*) as actual_pages from pipeline.source_pages group by version_id
)
select d.version_id from {{ ref('document_candidates') }} d
left join public.dim_company c on c.company_id = d.company_id
left join public.dim_source s on s.source_id = d.source_id
left join page_counts p on p.version_id = d.version_id
where c.company_id is null or s.source_id is null or s.source_url is distinct from d.source_url
   or d.page_count < 1 or p.actual_pages is distinct from d.page_count::bigint
   or length(d.content_sha256) <> 64 or d.review_status <> 'automatically_extracted'
   or d.extraction_status not in ('text_extracted', 'needs_ocr', 'structured_extracted')
