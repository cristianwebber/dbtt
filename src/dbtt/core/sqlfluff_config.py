"""Resolve which sqlfluff config governs a run.

Policy (as requested): if the project ships its own ``.sqlfluff`` we get out of
the way entirely and let sqlfluff discover it. Only when the project has no
config of its own do we apply dbtt's bundled opinionated ruleset. The two are
never merged — a user config fully replaces the defaults.
"""

from __future__ import annotations

import configparser
import io
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from .config import DbttConfig

USER_CONFIG_NAMES = (".sqlfluff",)

_COMMA_SECTION = "sqlfluff:layout:type:comma"
_KEYWORDS_SECTION = "sqlfluff:rules:capitalisation.keywords"


@dataclass
class ResolvedConfig:
    source: str  # "user" or "bundled"


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


def bundled_config_text() -> str:
    """The packaged default ruleset as text (works for zipped installs too)."""
    return files("dbtt.rules").joinpath("default.sqlfluff").read_text(encoding="utf-8")


def resolve_config(start: Path, project_root: Path | None) -> ResolvedConfig:
    user = _find_user_config(start, project_root)
    return ResolvedConfig(source="user" if user is not None else "bundled")


def render_bundled_config(config: DbttConfig) -> str:
    """Return the bundled sqlfluff ruleset as text, with dbtt toggles applied.

    The static base ``.sqlfluff`` is loaded and the two user-facing switches
    (comma placement, keyword casing) are overlaid on top, so a user's
    ``[tool.dbtt]`` settings change the effective ruleset without editing it.
    """
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # type: ignore[assignment]  # preserve key casing exactly
    parser.read_string(bundled_config_text())

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

    buffer = io.StringIO()
    parser.write(buffer)
    return buffer.getvalue()
