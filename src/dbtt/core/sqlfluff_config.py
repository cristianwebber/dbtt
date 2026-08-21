"""Resolve which sqlfluff config governs a run.

Policy (as requested): if the project ships its own ``.sqlfluff`` we get out of
the way entirely and let sqlfluff discover it. Only when the project has no
config of its own do we apply dbtt's bundled opinionated ruleset. The two are
never merged — a user config fully replaces the defaults.
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path

from .config import DbttConfig

USER_CONFIG_NAMES = (".sqlfluff",)

_COMMA_SECTION = "sqlfluff:layout:type:comma"
_KEYWORDS_SECTION = "sqlfluff:rules:capitalisation.keywords"


@dataclass
class ResolvedConfig:
    source: str  # "user" or "bundled"
    path: Path | None  # bundled config path to pass via --config; None when user-owned


def _find_user_config(start: Path, stop: Path | None) -> Path | None:
    """Walk up from ``start`` looking for a user .sqlfluff, not past ``stop``."""
    start = start.resolve()
    boundary = stop.resolve() if stop else None
    for directory in [start, *start.parents]:
        for name in USER_CONFIG_NAMES:
            candidate = directory / name
            if candidate.exists():
                return candidate
        if boundary is not None and directory == boundary:
            break
    return None


def bundled_config_path() -> Path:
    """Filesystem path to the packaged default ruleset."""
    resource = files("dbtt.rules") / "default.sqlfluff"
    # as_file materializes the resource if the package is zipped; for a normal
    # (unzipped) install it returns the real path.
    with as_file(resource) as path:
        return Path(path)


def resolve_config(start: Path, project_root: Path | None) -> ResolvedConfig:
    user = _find_user_config(start, project_root)
    if user is not None:
        return ResolvedConfig(source="user", path=None)
    return ResolvedConfig(source="bundled", path=bundled_config_path())


def render_bundled_config(config: DbttConfig) -> str:
    """Return the bundled sqlfluff ruleset as text, with dbtt toggles applied.

    The static base ``.sqlfluff`` is loaded and the two user-facing switches
    (comma placement, keyword casing) are overlaid on top, so a user's
    ``[tool.dbtt]`` settings change the effective ruleset without editing it.
    """
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # preserve key casing exactly
    parser.read(bundled_config_path(), encoding="utf-8")

    if not parser.has_section(_COMMA_SECTION):
        parser.add_section(_COMMA_SECTION)
    parser.set(_COMMA_SECTION, "line_position", config.commas)

    if not parser.has_section(_KEYWORDS_SECTION):
        parser.add_section(_KEYWORDS_SECTION)
    parser.set(
        _KEYWORDS_SECTION,
        "capitalisation_policy",
        "upper" if config.uppercase_keywords else "lower",
    )

    import io

    buffer = io.StringIO()
    parser.write(buffer)
    return buffer.getvalue()
