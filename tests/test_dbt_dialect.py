"""Dialect detection from dbt profiles."""

from __future__ import annotations

import pytest

from dbtt.core.dbt_dialect import adapter_to_dialect, detect_dialect
from dbtt.core.dbt_project import find_project


def _project(tmp_path, profile="demo", target="dev", adapter="duckdb"):
    (tmp_path / "dbt_project.yml").write_text(
        f"name: demo\nprofile: {profile}\n"
    )
    (tmp_path / "profiles.yml").write_text(
        f"{profile}:\n"
        f"  target: {target}\n"
        "  outputs:\n"
        f"    {target}:\n"
        f"      type: {adapter}\n"
    )
    return find_project(tmp_path)


@pytest.mark.parametrize(
    "adapter,expected",
    [
        ("duckdb", "duckdb"),
        ("snowflake", "snowflake"),
        ("bigquery", "bigquery"),
        ("spark", "sparksql"),
        ("sqlserver", "tsql"),
        ("synapse", "tsql"),
        ("something_new", "something_new"),  # unknown falls through to itself
    ],
)
def test_adapter_mapping(adapter, expected):
    assert adapter_to_dialect(adapter) == expected


def test_detect_from_profile(tmp_path):
    project = _project(tmp_path, adapter="snowflake")
    assert detect_dialect(project) == "snowflake"


def test_detect_uses_target(tmp_path):
    (tmp_path / "dbt_project.yml").write_text("name: demo\nprofile: demo\n")
    (tmp_path / "profiles.yml").write_text(
        "demo:\n"
        "  target: prod\n"
        "  outputs:\n"
        "    dev:\n"
        "      type: duckdb\n"
        "    prod:\n"
        "      type: snowflake\n"
    )
    project = find_project(tmp_path)
    assert detect_dialect(project) == "snowflake"


def test_detect_none_without_profile(tmp_path):
    (tmp_path / "dbt_project.yml").write_text("name: demo\n")
    project = find_project(tmp_path)
    assert detect_dialect(project) is None


def test_detect_none_without_profiles_file(tmp_path):
    (tmp_path / "dbt_project.yml").write_text("name: demo\nprofile: demo\n")
    project = find_project(tmp_path)
    assert detect_dialect(project) is None


def test_detect_none_when_profiles_unparseable(tmp_path):
    # A profiles.yml dbtt can't parse must degrade gracefully to None, not raise.
    (tmp_path / "dbt_project.yml").write_text("name: demo\nprofile: demo\n")
    (tmp_path / "profiles.yml").write_text("demo: {this is : not valid yaml\n")
    project = find_project(tmp_path)
    assert detect_dialect(project) is None


def test_detect_none_when_profile_name_absent_from_profiles(tmp_path):
    (tmp_path / "dbt_project.yml").write_text("name: demo\nprofile: missing\n")
    (tmp_path / "profiles.yml").write_text(
        "other:\n  target: dev\n  outputs:\n    dev:\n      type: duckdb\n"
    )
    project = find_project(tmp_path)
    assert detect_dialect(project) is None


def test_detect_env_profiles_dir(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "dbt_project.yml").write_text("name: demo\nprofile: demo\n")
    profiles_dir = tmp_path / "cfg"
    profiles_dir.mkdir()
    (profiles_dir / "profiles.yml").write_text(
        "demo:\n  target: dev\n  outputs:\n    dev:\n      type: postgres\n"
    )
    monkeypatch.setenv("DBT_PROFILES_DIR", str(profiles_dir))
    project = find_project(proj)
    assert detect_dialect(project) == "postgres"
