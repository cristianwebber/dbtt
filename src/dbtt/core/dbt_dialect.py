"""Detect the sqlfluff dialect from a dbt project's profile.

dbt already knows which warehouse a project targets — it's the adapter ``type``
in ``profiles.yml``. Rather than make the user restate it, dbtt reads that and
maps it to the matching sqlfluff dialect, so linting works for any warehouse out
of the box. Detection is best-effort: if the profile can't be found or read, the
caller falls back to an explicit ``--dialect``.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import yaml_io
from .dbt_project import DbtProject

PROFILES_FILE = "profiles.yml"

# dbt adapter type -> sqlfluff dialect. Most are 1:1; the rest are mapped
# explicitly. Unknown types fall through to the type name itself, since sqlfluff
# dialect names usually match the adapter name.
ADAPTER_TO_DIALECT = {
    "snowflake": "snowflake",
    "bigquery": "bigquery",
    "postgres": "postgres",
    "redshift": "redshift",
    "duckdb": "duckdb",
    "databricks": "databricks",
    "spark": "sparksql",
    "trino": "trino",
    "athena": "athena",
    "clickhouse": "clickhouse",
    "mysql": "mysql",
    "sqlserver": "tsql",
    "synapse": "tsql",
    "fabric": "tsql",
    "hive": "hive",
    "exasol": "exasol",
    "teradata": "teradata",
    "vertica": "vertica",
    "greenplum": "greenplum",
    "materialize": "materialize",
    "duckdb_wasm": "duckdb",
}


def _profiles_search_paths(project: DbtProject) -> list[Path]:
    paths: list[Path] = []
    env_dir = os.environ.get("DBT_PROFILES_DIR")
    if env_dir:
        paths.append(Path(env_dir).expanduser() / PROFILES_FILE)
    paths.append(project.root / PROFILES_FILE)
    paths.append(Path.home() / ".dbt" / PROFILES_FILE)
    return paths


def _adapter_type_from_profiles(profiles: dict, profile_name: str) -> str | None:
    block = profiles.get(profile_name)
    if not isinstance(block, dict):
        return None
    outputs = block.get("outputs")
    if not isinstance(outputs, dict) or not outputs:
        return None
    target = block.get("target")
    output = outputs.get(target) if target else None
    if not isinstance(output, dict):
        # No/invalid target: fall back to the sole output if unambiguous.
        if len(outputs) == 1:
            output = next(iter(outputs.values()))
        else:
            return None
    type_ = output.get("type") if isinstance(output, dict) else None
    return str(type_) if type_ else None


def adapter_to_dialect(adapter_type: str) -> str:
    return ADAPTER_TO_DIALECT.get(adapter_type.lower(), adapter_type.lower())


def detect_dialect(project: DbtProject) -> str | None:
    """Return the sqlfluff dialect for ``project``, or None if undetectable."""
    if not project.profile:
        return None
    for candidate in _profiles_search_paths(project):
        if not candidate.exists():
            continue
        try:
            profiles = yaml_io.load(candidate)
        except Exception:
            continue
        if not isinstance(profiles, dict):
            continue
        adapter_type = _adapter_type_from_profiles(profiles, project.profile)
        if adapter_type:
            return adapter_to_dialect(adapter_type)
    return None
