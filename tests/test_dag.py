import pytest

pytest.importorskip("airflow", reason="Airflow is only installed in the Astro image")

from airflow.models import DagBag  # noqa: E402

EXPECTED_TASKS = {
    "load_postgres",
    "fivetran_sync",
    "dbt_run",
    "dbt_test",
    "hightouch_sync",
    "refresh_metrics",
    "build_dashboard",
}


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(dag_folder="dags", include_examples=False)


def test_dag_imports_without_error(dagbag):
    assert dagbag.import_errors == {}


def test_dag_exists(dagbag):
    assert "gtm_pipeline" in dagbag.dags


def test_dag_has_every_task(dagbag):
    dag = dagbag.dags["gtm_pipeline"]
    assert {t.task_id for t in dag.tasks} == EXPECTED_TASKS


def test_dag_runs_in_the_correct_order(dagbag):
    dag = dagbag.dags["gtm_pipeline"]

    def downstream(task_id):
        return {t.task_id for t in dag.get_task(task_id).downstream_list}

    assert downstream("load_postgres") == {"fivetran_sync"}
    assert downstream("fivetran_sync") == {"dbt_run"}
    assert downstream("dbt_run") == {"dbt_test"}
    assert downstream("dbt_test") == {"hightouch_sync"}
    assert downstream("hightouch_sync") == {"refresh_metrics"}
    assert downstream("refresh_metrics") == {"build_dashboard"}


def test_dag_does_not_backfill(dagbag):
    assert dagbag.dags["gtm_pipeline"].catchup is False


def test_dbt_test_failure_stops_publication(dagbag):
    # refresh_metrics must never run on a dbt_test failure, or the dashboard
    # could publish numbers that failed validation.
    dag = dagbag.dags["gtm_pipeline"]
    assert dag.get_task("refresh_metrics").trigger_rule == "all_success"
