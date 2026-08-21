"""Locate and read the surrounding ``dbt_project.yml``.

Everything dbtt does is relative to a dbt project. This module finds the
project root by walking up from a starting directory and exposes the handful of
settings the toolkit needs (project name, model paths). It intentionally does
*not* try to fully model dbt's config — dbt-core remains the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import yaml_io

PROJECT_FILE = "dbt_project.yml"
DEFAULT_MODEL_PATHS = ["models"]


@dataclass
class DbtProject:
    root: Path
    name: str
    model_paths: list[str]

    @property
    def model_dirs(self) -> list[Path]:
        return [self.root / p for p in self.model_paths]

    def is_under_models(self, path: Path) -> bool:
        path = path.resolve()
        return any(
            path == d.resolve() or d.resolve() in path.resolve().parents
            for d in self.model_dirs
        )


def find_project(start: Path | None = None) -> DbtProject | None:
    """Walk upward from ``start`` (default cwd) looking for a dbt project."""
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        candidate = directory / PROJECT_FILE
        if candidate.exists():
            return _load(candidate)
    return None


def _load(project_file: Path) -> DbtProject:
    data = yaml_io.load(project_file) or {}
    model_paths = data.get("model-paths") or DEFAULT_MODEL_PATHS
    return DbtProject(
        root=project_file.parent,
        name=str(data.get("name", project_file.parent.name)),
        model_paths=list(model_paths),
    )
