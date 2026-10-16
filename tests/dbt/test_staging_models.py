"""The staging models read every raw column by name.

A column that 04_raw_datasets.sql and sec_backfill rename or drop fails here,
before dbt reaches Snowflake; the raw DDL and sec_backfill are held together
by tests/include/test_sec_backfill.py.
"""

import re
from pathlib import Path

import pytest
import yaml

from include import sec_backfill
from include.sec_profile import TABLES

STAGING = Path(__file__).resolve().parents[2] / "dbt" / "models" / "staging"


def words(sql: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", sql.lower()))


@pytest.mark.parametrize("table", TABLES)
def test_each_raw_column_is_read_by_its_staging_model(table: str):
    model = STAGING / f"stg_dataset_{table.lower()}.sql"

    read = words(model.read_text())

    for column in sec_backfill.COLUMNS[table] + sec_backfill.SOURCE_COLUMNS:
        assert column in read, f"{model.name} does not read {column}"


def test_the_sources_name_every_raw_table_and_nothing_else():
    sources = yaml.safe_load((STAGING / "sources.yml").read_text())

    named = {table["name"] for table in sources["sources"][0]["tables"]}

    assert named == {f"dataset_{table.lower()}" for table in TABLES} | {"parsed_filings"}


def test_every_staging_model_is_described_and_tested():
    described = {
        model["name"] for model in yaml.safe_load((STAGING / "staging.yml").read_text())["models"]
    }

    on_disk = {path.stem for path in STAGING.glob("stg_*.sql")}

    assert described == on_disk
