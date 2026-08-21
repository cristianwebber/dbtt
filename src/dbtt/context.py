"""Shared, lazily-discovered project context for dbtt commands.

Commands receive a :class:`Context` (via Typer's context object) so that project
discovery happens once per invocation. Commands that can operate on arbitrary
paths still work when no dbt project is found — ``project`` is simply ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .core.dbt_project import DbtProject, find_project


@dataclass
class Context:
    cwd: Path = field(default_factory=Path.cwd)
    _project: DbtProject | None = field(default=None, init=False)
    _resolved: bool = field(default=False, init=False)

    @property
    def project(self) -> DbtProject | None:
        if not self._resolved:
            self._project = find_project(self.cwd)
            self._resolved = True
        return self._project
