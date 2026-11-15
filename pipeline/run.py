"""Capture registered sources, stage immutable versions and publish only after dbt tests."""
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4

from pipeline.processing import ALLOWED_FORMATS, extract_document, fetch_source

ROOT = Path(__file__).resolve().parent
LOG = logging.getLogger("vietgreen.pipeline")
FIELDS = ("version_id", "source_id", "company_id", "source_url", "title", "source_type",
          "content_sha256", "object_key", "content_type", "fetched_at", "page_count",
          "extraction_status", "review_status")


def utcnow():
    return datetime.now(timezone.utc)


def load_sources(path=ROOT / "sources.json"):
    """Read the explicit source registry; identifiers map to existing warehouse dimensions."""
    sources = json.loads(Path(path).read_text(encoding="utf-8"))
    seen = set()
    for source in sources:
        for field in ("source_id", "company_id", "title", "url", "format", "source_type"):
            if not isinstance(source.get(field), str) or not source[field].strip():
                raise ValueError("Missing source configuration field: " + field)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", source["source_id"]):
            raise ValueError("Invalid source ID")
        if source["source_id"] in seen:
            raise ValueError("Duplicate source ID")
        if source["format"] not in ALLOWED_FORMATS:
            raise ValueError("Unsupported source format")
        seen.add(source["source_id"])
    if not sources:
        raise ValueError("The source registry is empty")
    return sources


def storage_client():
    """Build an S3 client from environment-only credentials."""
    from minio import Minio
    return Minio(os.environ["MINIO_ENDPOINT"], access_key=os.environ["MINIO_ACCESS_KEY"],
                 secret_key=os.environ["MINIO_SECRET_KEY"],
                 secure=os.getenv("MINIO_SECURE", "true").lower() == "true")


def put_bytes(client, bucket, key, body, content_type):
    client.put_object(bucket, key, io.BytesIO(body), len(body), content_type=content_type)


def ensure_raw_object(client, bucket, key, body, content_type, already_recorded):
    """Restore a missing raw object from matching downloaded bytes, or fail on storage errors."""
    from minio.error import S3Error
    if already_recorded:
        try:
            client.stat_object(bucket, key)
            return
        except S3Error as exc:
            if exc.code not in ("NoSuchKey", "NoSuchObject"):
                raise
    put_bytes(client, bucket, key, body, content_type)


def run_dbt(run_id):
    """Build candidate views and execute data tests before touching published data."""
    variables = json.dumps({"run_id": run_id})
    for command in ("run", "test"):
        subprocess.run([str(Path(sys.executable).parent / "dbt"), command, "--project-dir", str(ROOT / "dbt"),
                        "--profiles-dir", str(ROOT / "dbt"), "--vars", variables], check=True)


def publish(conn, run_id):
    """Publish the tested snapshot and mark the run successful atomically."""
    columns = ", ".join(FIELDS)
    update = ", ".join(f"{col} = EXCLUDED.{col}" for col in FIELDS if col != "source_id")
    with conn.transaction():
        result = conn.execute(f"""INSERT INTO public.pipeline_document_evidence ({columns}, published_at)
            SELECT {columns}, now() FROM pipeline_transform.document_candidates
            WHERE source_id = (SELECT source_id FROM pipeline.ingestion_runs WHERE run_id=%s)
            ON CONFLICT (source_id) DO UPDATE SET {update}, published_at = EXCLUDED.published_at""", (run_id,))
        if result.rowcount != 1:
            raise ValueError("Exactly one validated candidate is required for publication")
        conn.execute("UPDATE pipeline.ingestion_runs SET status='success', completed_at=now() WHERE run_id=%s", (run_id,))


def ingest(source, client, bucket, connect):
    """Record a run, store raw bytes, stage pages and publish validated data."""
    from psycopg.types.json import Jsonb
    run_id = str(uuid4())
    source_id = source["source_id"]
    # Separate autocommit connection retains an advisory lock through fetch, dbt and publish.
    with connect(autocommit=True) as lock:
        if not lock.execute("SELECT pg_try_advisory_lock(89817504)").fetchone()[0]:
            raise RuntimeError("Another VietGreen evidence run is active; retry later")
        with connect(autocommit=True) as conn:
            conn.execute((ROOT / "schema.sql").read_text())
            conn.execute("INSERT INTO pipeline.ingestion_runs (run_id,source_id,started_at,status) VALUES (%s,%s,%s,'running')", (run_id, source_id, utcnow()))
            try:
                LOG.info("event=fetch_started run_id=%s source_id=%s", run_id, source_id)
                body, content_type, final_url = fetch_source(source["url"])
                digest = hashlib.sha256(body).hexdigest()
                version_id = hashlib.sha256((source_id + ":" + digest).encode()).hexdigest()
                observed_at = utcnow()
                existing = conn.execute("SELECT object_key FROM pipeline.source_versions WHERE version_id=%s", (version_id,)).fetchone()
                if not client.bucket_exists(bucket):
                    client.make_bucket(bucket)
                key = existing[0] if existing else (f"sources/{source_id}/{observed_at:%Y/%m/%dT%H%M%SZ}/{digest}.{source['format']}")
                ensure_raw_object(client, bucket, key, body, content_type, bool(existing))
                metadata = {"run_id": run_id, "source_id": source_id, "company_id": source["company_id"],
                            "source_url": source["url"], "resolved_url": final_url,
                            "fetched_at": observed_at.isoformat(), "sha256": digest,
                            "object_key": key, "content_type": content_type, "size_bytes": len(body)}
                put_bytes(client, bucket, f"acquisitions/{source_id}/{run_id}.json",
                          json.dumps(metadata, ensure_ascii=False).encode(), "application/json")
                if not existing:
                    pages, status = extract_document(body, source["format"])
                    with conn.transaction():
                        conn.execute("""INSERT INTO pipeline.source_versions
                            (version_id,source_id,company_id,source_url,title,source_type,content_sha256,object_key,
                             content_type,fetched_at,page_count,extraction_status,review_status)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'automatically_extracted')""",
                            (version_id, source_id, source["company_id"], source["url"], source["title"],
                             source["source_type"], digest, key, content_type, observed_at, len(pages), status))
                        with conn.cursor() as cursor:
                            cursor.executemany("INSERT INTO pipeline.source_pages VALUES (%s,%s,%s,%s)",
                                [(version_id, p["page_number"], p["text"], Jsonb(p["tables"])) for p in pages])
                conn.execute("INSERT INTO pipeline.acquisitions VALUES (%s,%s,%s)", (run_id, version_id, observed_at))
                run_dbt(run_id)
                publish(conn, run_id)
                LOG.info("event=published run_id=%s source_id=%s version_id=%s reused=%s", run_id, source_id, version_id, bool(existing))
                return run_id
            except Exception as exc:
                conn.execute("UPDATE pipeline.ingestion_runs SET status='failed', completed_at=now(), error_summary=%s WHERE run_id=%s", (str(exc)[:1000], run_id))
                LOG.exception("event=failed run_id=%s source_id=%s", run_id, source_id)
                raise


def main():
    """Execute the registry in order; an exception exits nonzero for Airflow retries."""
    import psycopg
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sources = load_sources()
    selected = sys.argv[1:]  # Optional source IDs, useful for retries.
    if selected:
        sources = [s for s in sources if s["source_id"] in selected]
        if set(selected) != {s["source_id"] for s in sources}:
            raise ValueError("Unknown source ID")
    client = storage_client()
    for source in sources:
        ingest(source, client, os.getenv("MINIO_BUCKET", "vietgreen-raw"),
               lambda **kw: psycopg.connect(os.environ["DATABASE_URL"], **kw))


if __name__ == "__main__":
    main()
