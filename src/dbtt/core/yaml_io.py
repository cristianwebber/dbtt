"""Comment- and order-preserving YAML I/O built on ruamel.yaml.

dbt schema files are hand-maintained: they carry comments, deliberate key
ordering, and descriptions. pyyaml's ``safe_load``/``dump`` round-trip destroys
all of that, so every helper here goes through ruamel's round-trip API instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML


def _yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    # dbt files routinely have long descriptions; don't hard-wrap them.
    yaml.width = 4096
    return yaml


def load(path: str | Path) -> Any:
    """Load a YAML file preserving comments/order. Returns None for empty files."""
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return None
    with path.open("r", encoding="utf-8") as fh:
        return _yaml().load(fh)


def dump(data: Any, path: str | Path) -> None:
    """Write ``data`` back to ``path`` preserving comments/order."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        _yaml().dump(data, fh)
