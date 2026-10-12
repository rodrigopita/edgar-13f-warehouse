import importlib.util
from pathlib import Path

import pytest

DAG_FILE = Path(__file__).resolve().parents[2] / "dags" / "sec_datasets_backfill.py"


@pytest.fixture(scope="module")
def dag():
    spec = importlib.util.spec_from_file_location("sec_datasets_backfill", DAG_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.sec_datasets_backfill()


def test_runs_only_by_hand(dag):
    assert dag.dag_id == "sec_datasets_backfill"
    assert dag.schedule is None
    assert dag.catchup is False
    assert dag.max_active_runs == 1


def test_only_the_tasks_that_call_the_sec_are_in_the_edgar_pool(dag):
    pools = {t.task_id: t.pool for t in dag.tasks}

    assert pools == {
        "list_datasets": "edgar",
        "stage_dataset": "edgar",
        "copy_table": "default_pool",
        "record_audit": "default_pool",
    }


def test_copy_runs_after_every_zip_is_staged_and_the_audit_runs_regardless(dag):
    downstream = {t.task_id: sorted(t.downstream_task_ids) for t in dag.tasks}

    assert downstream["list_datasets"] == ["stage_dataset"]
    assert downstream["stage_dataset"] == ["copy_table", "record_audit"]
    assert downstream["copy_table"] == ["record_audit"]
    assert dag.get_task("record_audit").trigger_rule == "all_done"
    assert dag.get_task("copy_table").retries == 0
