"""Resolve which sqlfluff config governs a run.

Policy (as requested): if the project ships its own ``.sqlfluff`` we get out of
the way entirely and let sqlfluff discover it. Only when the project has no
config of its own do we apply dbtt's bundled opinionated ruleset. The two are
never merged — a user config fully replaces the defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path

USER_CONFIG_NAMES = (".sqlfluff",)


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
