import pytest

pytest.importorskip("airflow", reason="Airflow is only installed in the Astro image")

from airflow.models import DagBag  # noqa: E402

EXPECTED_TASKS = {"fivetran_sync", "dbt_run", "dbt_test", "hightouch_sync"}


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(dag_folder="dags", include_examples=False)


def test_dag_imports_without_error(dagbag):
    assert dagbag.import_errors == {}


def test_dag_exists_and_is_scheduled(dagbag):
    dag = dagbag.dags["gtm_pipeline"]
    assert dag.schedule == "0 13 * * *"
    assert dag.catchup is False


def test_dag_has_every_task(dagbag):
    dag = dagbag.dags["gtm_pipeline"]
    assert {t.task_id for t in dag.tasks} == EXPECTED_TASKS


def test_dag_runs_in_the_correct_order(dagbag):
    dag = dagbag.dags["gtm_pipeline"]

    def downstream(task_id):
        return {t.task_id for t in dag.get_task(task_id).downstream_list}

    assert downstream("fivetran_sync") == {"dbt_run"}
    assert downstream("dbt_run") == {"dbt_test"}
    assert downstream("dbt_test") == {"hightouch_sync"}
    assert downstream("hightouch_sync") == set()


def test_dbt_test_failure_stops_activation(dagbag):
    # Hightouch must never sync marts that failed validation.
    dag = dagbag.dags["gtm_pipeline"]
    assert dag.get_task("hightouch_sync").trigger_rule == "all_success"


def test_single_active_run(dagbag):
    # The local refresh triggers runs too; two overlapping runs would race dbt.
    assert dagbag.dags["gtm_pipeline"].max_active_runs == 1
