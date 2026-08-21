"""Enforce the "one YAML file per model" convention.

Each model ``<name>.sql`` should be documented by a sibling ``<name>.yml`` that
contains exactly that one model. Keeping each model's docs in its own small,
self-contained file is easier to review and far easier for LLMs to process than
one giant shared schema file.

This module is pure: the command layer parses the YAML and passes in the model
names each file declares, so the rules stay trivially unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Violation kinds.
MULTIPLE_MODELS = "multiple_models"
MISNAMED = "misnamed"
MISSING = "missing"


@dataclass
class Violation:
    path: Path
    kind: str
    message: str


def check(sql_files: list[Path], yml_models: dict[Path, list[str]]) -> list[Violation]:
    """Return convention violations.

    Args:
        sql_files: model ``.sql`` paths in scope.
        yml_models: each schema YAML path mapped to the model names it declares
            (files that declare no models are simply omitted by the caller).

    Rules, each reported once (a model in a shared file is covered by the file's
    MULTIPLE_MODELS violation, not also flagged MISSING):
      * MULTIPLE_MODELS — a YAML file declares more than one model.
      * MISNAMED — a single-model YAML file whose name doesn't match its model.
      * MISSING — a model no YAML file documents at all.
    """
    violations: list[Violation] = []
    documented: set[str] = set()

    for yml_path, names in yml_models.items():
        documented.update(names)
        if len(names) > 1:
            violations.append(
                Violation(
                    yml_path,
                    MULTIPLE_MODELS,
                    f"documents {len(names)} models ({', '.join(names)}); "
                    "split into one file per model",
                )
            )
        elif len(names) == 1 and yml_path.stem != names[0]:
            violations.append(
                Violation(
                    yml_path,
                    MISNAMED,
                    f"documents model '{names[0]}' but should be named '{names[0]}.yml'",
                )
            )

    for sql in sql_files:
        if sql.stem not in documented:
            violations.append(
                Violation(
                    sql.with_suffix(".yml"), MISSING, f"model '{sql.stem}' is undocumented"
                )
            )

    return violations
