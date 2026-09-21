"""The full GTM pipeline run, once a day.

load Postgres -> Fivetran sync -> dbt run -> dbt test ->
Hightouch sync -> refresh metrics -> rebuild the dashboard.

There is deliberately no harvest task here. The ATS harvester lives in a
separate repo and is not vendored into this one, so the pipeline starts from
whatever the harvester has already written to Postgres. This is an intentional
omission, not an oversight.

Every task shells out to a CLI that is independently testable and
independently runnable, so a failure is debuggable outside Airflow.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_DIR = os.environ.get("NERDJOY_PROJECT_DIR", "/usr/local/airflow")

default_args = {
    "owner": "nerdjoy",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="gtm_pipeline",
    description="Run the job-search GTM pipeline end to end",
    start_date=datetime(2026, 9, 1),
    schedule="0 13 * * *",
    catchup=False,
    default_args=default_args,
    tags=["gtm", "nerdjoy"],
) as dag:
    load_postgres = BashOperator(
        task_id="load_postgres",
        bash_command=f"cd {PROJECT_DIR} && python3 -m nerdjoy_pipeline.pg_loader",
    )

    fivetran_sync = BashOperator(
        task_id="fivetran_sync",
        bash_command=(
            "curl -sS -X POST --fail "
            "-u \"$FIVETRAN_API_KEY:$FIVETRAN_API_SECRET\" "
            "\"https://api.fivetran.com/v1/connectors/$FIVETRAN_CONNECTOR_ID_POSTGRES/force\""
        ),
        doc_md="Trigger the Postgres connector. HubSpot syncs on its own schedule.",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {PROJECT_DIR}/dbt && dbt run",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {PROJECT_DIR}/dbt && dbt test",
        doc_md="Gate. Nothing downstream publishes if the marts fail validation.",
    )

    hightouch_sync = BashOperator(
        task_id="hightouch_sync",
        bash_command=(
            "curl -sS -X POST --fail "
            "-H \"Authorization: Bearer $HIGHTOUCH_API_KEY\" "
            "-H 'Content-Type: application/json' "
            "\"https://api.hightouch.com/api/v1/syncs/$HIGHTOUCH_SYNC_ID_SHEET/trigger\" "
            "-d '{\"fullResync\": false}'"
        ),
    )

    refresh_metrics = BashOperator(
        task_id="refresh_metrics",
        bash_command=(
            f"cd {PROJECT_DIR} && "
            "python3 -m nerdjoy_pipeline.metrics_extract --source bigquery --output metrics.json"
        ),
        doc_md="Runs the anonymization guard. A guard failure exits non-zero and stops the run.",
    )

    build_dashboard = BashOperator(
        task_id="build_dashboard",
        bash_command=f"cd {PROJECT_DIR} && python3 dashboard/build.py",
    )

    (
        load_postgres
        >> fivetran_sync
        >> dbt_run
        >> dbt_test
        >> hightouch_sync
        >> refresh_metrics
        >> build_dashboard
    )
