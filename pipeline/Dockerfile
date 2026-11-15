FROM apache/airflow:2.10.5-python3.11
COPY pipeline/requirements.txt /tmp/pipeline-requirements.txt
RUN python -m venv /home/airflow/vietgreen-venv \
    && /home/airflow/vietgreen-venv/bin/pip install --no-cache-dir -r /tmp/pipeline-requirements.txt
COPY pipeline /opt/vietgreen/pipeline
ENV PYTHONPATH=/opt/vietgreen DBT_PROFILES_DIR=/opt/vietgreen/pipeline/dbt
WORKDIR /opt/vietgreen
