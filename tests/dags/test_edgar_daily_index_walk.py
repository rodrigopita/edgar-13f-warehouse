import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

DAG_FILE = Path(__file__).resolve().parents[2] / "dags" / "edgar_daily_index_walk.py"


@pytest.fixture(scope="module")
def dag():
    spec = importlib.util.spec_from_file_location("edgar_daily_index_walk", DAG_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.edgar_daily_index_walk()


def test_schedule_and_catchup_follow_the_scope_decisions(dag):
    assert dag.dag_id == "edgar_daily_index_walk"
    assert dag.schedule == "0 6 * * *"
    assert dag.catchup is True
    assert dag.max_active_runs == 1
    assert dag.start_date == datetime(2026, 9, 1, tzinfo=UTC)
    assert dag.dagrun_timeout == timedelta(hours=3)


def test_every_edgar_calling_task_is_in_the_one_slot_pool(dag):
    pools = {t.task_id: t.pool for t in dag.tasks}

    assert pools == {
        "plan_walk": "edgar",
        "land_indexes": "edgar",
        "walk_batch": "edgar",
        "record_audit": "default_pool",
    }


def test_the_audit_runs_whatever_happened_upstream(dag):
    assert dag.get_task("record_audit").trigger_rule == "all_done"
    assert dag.get_task("walk_batch").retries == 0


def test_task_graph(dag):
    downstream = {t.task_id: sorted(t.downstream_task_ids) for t in dag.tasks}

    assert downstream["plan_walk"] == ["land_indexes", "record_audit"]
    assert downstream["land_indexes"] == ["walk_batch"]
    assert downstream["walk_batch"] == ["record_audit"]
    assert downstream["record_audit"] == []
