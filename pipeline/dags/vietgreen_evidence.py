"""Scheduled acquisition: capture, process, validate, then publish evidence."""
from datetime import datetime, timedelta, timezone
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="vietgreen_evidence",
    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    schedule="0 2 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["vietgreen", "evidence"],
    doc_md="""Fetch registered evidence. A failure leaves the published snapshot unchanged;
    inspect task logs and pipeline.ingestion_runs before retrying.""",
) as dag:
    BashOperator(task_id="acquire_validate_publish", bash_command="/home/airflow/vietgreen-venv/bin/python -m pipeline.run")
