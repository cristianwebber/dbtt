"""dbtt's own configuration, read from standard TOML.

Users tune dbtt through a ``[tool.dbtt]`` table in ``pyproject.toml`` (the same
file that already configures ruff, pytest, ...) or a standalone ``dbtt.toml``.
No bespoke format — just TOML, discovered by walking up from the working
directory to the dbt project root.

Only the settings that shape the bundled sqlfluff ruleset live here today; the
table is the place future knobs will be added.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

STANDALONE_FILE = "dbtt.toml"
PYPROJECT_FILE = "pyproject.toml"

VALID_COMMAS = ("leading", "trailing")


class ConfigError(ValueError):
    """Raised when a dbtt config value is present but invalid."""


@dataclass
class DbttConfig:
    commas: str = "leading"
    uppercase_keywords: bool = True
    source: Path | None = None  # where the config was read from, if anywhere

    @classmethod
    def from_dict(cls, data: dict, source: Path | None) -> "DbttConfig":
        config = cls(source=source)
        unknown = set(data) - {"commas", "uppercase_keywords"}
        if unknown:
            raise ConfigError(
                f"unknown dbtt setting(s) {sorted(unknown)} in {source}; "
                "valid keys are 'commas', 'uppercase_keywords'"
            )
        if "commas" in data:
            commas = data["commas"]
            if commas not in VALID_COMMAS:
                raise ConfigError(
                    f"invalid commas={commas!r} in {source}; expected one of {VALID_COMMAS}"
                )
            config.commas = commas
        if "uppercase_keywords" in data:
            value = data["uppercase_keywords"]
            if not isinstance(value, bool):
                raise ConfigError(
                    f"invalid uppercase_keywords={value!r} in {source}; expected true/false"
                )
            config.uppercase_keywords = value
        return config


def _read_table(path: Path) -> dict | None:
    """Return the dbtt config table from ``path``, or None if it carries none."""
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    if path.name == PYPROJECT_FILE:
        table = data.get("tool", {}).get("dbtt")
        return table if isinstance(table, dict) else None
    # Standalone dbtt.toml: settings live at the top level (a [dbtt] table is
    # also accepted for people who prefer to nest it).
    if isinstance(data.get("dbtt"), dict):
        return data["dbtt"]
    return data or None


def find_config_file(start: Path, stop: Path | None) -> tuple[Path, dict] | None:
    """Walk up from ``start`` (not past ``stop``) for a dbtt config table.

    At each level a standalone ``dbtt.toml`` wins over ``pyproject.toml``.
    """
    start = start.resolve()
    boundary = stop.resolve() if stop else None
    for directory in [start, *start.parents]:
        standalone = directory / STANDALONE_FILE
        if standalone.exists():
            table = _read_table(standalone)
            if table is not None:
                return standalone, table
        pyproject = directory / PYPROJECT_FILE
        if pyproject.exists():
            table = _read_table(pyproject)
            if table is not None:
                return pyproject, table
        if boundary is not None and directory == boundary:
            break
    return None


def load_config(start: Path, project_root: Path | None) -> DbttConfig:
    """Load dbtt config, falling back to defaults when none is found."""
    found = find_config_file(start, project_root)
    if found is None:
        return DbttConfig()
    path, table = found
    return DbttConfig.from_dict(table, source=path)
