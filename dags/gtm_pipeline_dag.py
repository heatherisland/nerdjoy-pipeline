"""The cloud half of the GTM pipeline: Fivetran -> dbt run -> dbt test -> Hightouch.

Runs daily on Astro, and is also triggered by scripts/refresh.py right after a
new tracker export is loaded into Postgres. The tracker load, the privacy guard
and the dashboard publish stay local, because the tracker never leaves the
owner's machine and the guard needs the full, unfiltered tracker to build its
deny list. Building it from Postgres or BigQuery would inherit their filters.

dbt runs from its own virtualenv (see Dockerfile) so its dependencies never
conflict with Airflow's. Credentials arrive as deployment environment variables.
"""
from __future__ import annotations

import json
import os
import time
from base64 import b64encode
from datetime import datetime, timedelta, timezone

import requests
from airflow.exceptions import AirflowException
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import DAG

AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", "/usr/local/airflow")
DBT_DIR = f"{AIRFLOW_HOME}/dbt"
DBT_BIN = f"{AIRFLOW_HOME}/dbt_venv/bin/dbt"

# The key arrives as a JSON string in GCP_SA_KEY_JSON; dbt's service-account
# method wants a file, so write one readable only by this process.
DBT_CMD = (
    "set -euo pipefail; umask 077; "
    'KEY=$(mktemp); trap "rm -f $KEY" EXIT; '
    'printf "%s" "$GCP_SA_KEY_JSON" > "$KEY"; '
    f'cd {DBT_DIR} && GOOGLE_APPLICATION_CREDENTIALS="$KEY" DBT_PROFILES_DIR={DBT_DIR}/airflow '
    f"{DBT_BIN} {{cmd}} --target-path /tmp/dbt_target --log-path /tmp/dbt_logs"
)


def _parse_ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def fivetran_sync() -> None:
    cid = os.environ["FIVETRAN_CONNECTOR_ID_POSTGRES"]
    token = b64encode(
        f"{os.environ['FIVETRAN_API_KEY']}:{os.environ['FIVETRAN_API_SECRET']}".encode()
    ).decode()
    headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}
    base = f"https://api.fivetran.com/v1/connections/{cid}"
    started = datetime.now(timezone.utc)
    requests.post(f"{base}/sync", headers=headers, json={"force": True}, timeout=60).raise_for_status()
    deadline = time.time() + 30 * 60
    while time.time() < deadline:
        time.sleep(30)
        data = requests.get(base, headers=headers, timeout=60).json().get("data", {})
        failed, done = _parse_ts(data.get("failed_at")), _parse_ts(data.get("succeeded_at"))
        if failed and failed > started:
            raise AirflowException("Fivetran sync failed")
        if done and done > started:
            print(f"Fivetran sync succeeded at {done.isoformat()}")
            return
    raise AirflowException("Fivetran sync did not finish within 30 minutes")


def hightouch_sync() -> None:
    sync_id = os.environ["HIGHTOUCH_SYNC_ID_SHEET"]
    headers = {"Authorization": f"Bearer {os.environ['HIGHTOUCH_API_KEY']}"}
    base = f"https://api.hightouch.com/api/v1/syncs/{sync_id}"
    resp = requests.post(f"{base}/trigger", headers=headers, json={"fullResync": False}, timeout=60)
    resp.raise_for_status()
    run_id = str(resp.json()["id"])
    deadline = time.time() + 15 * 60
    while time.time() < deadline:
        time.sleep(20)
        runs = requests.get(f"{base}/runs", headers=headers, params={"runId": run_id}, timeout=60)
        data = runs.json().get("data", [])
        status = data[0].get("status") if data else None
        if status == "success":
            print(json.dumps({"status": status, "rows": data[0].get("querySize")}))
            return
        if status in ("failed", "cancelled", "warning", "interrupted"):
            raise AirflowException(f"Hightouch sync {status}")
    raise AirflowException("Hightouch sync did not finish within 15 minutes")


with DAG(
    dag_id="gtm_pipeline",
    description="Fivetran sync, dbt run and test, Hightouch activation",
    start_date=datetime(2026, 9, 1),
    schedule="0 13 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "nerdjoy", "retries": 1, "retry_delay": timedelta(minutes=5)},
    tags=["gtm", "nerdjoy"],
) as dag:
    sync = PythonOperator(task_id="fivetran_sync", python_callable=fivetran_sync)
    dbt_run = BashOperator(task_id="dbt_run", bash_command=DBT_CMD.format(cmd="run"))
    dbt_test = BashOperator(task_id="dbt_test", bash_command=DBT_CMD.format(cmd="test"))
    activate = PythonOperator(task_id="hightouch_sync", python_callable=hightouch_sync)

    sync >> dbt_run >> dbt_test >> activate
