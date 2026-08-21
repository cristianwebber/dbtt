"""Build and merge dbt schema (properties) YAML for models.

The generator is deliberately *additive and non-destructive*: when a schema
file already exists it keeps every hand-written description, test, and column
in place, and only fills in what is missing (new models, newly added columns).
That is what makes it safe to run repeatedly in a real project.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .sql_columns import ColumnExtraction, extract_columns


@dataclass
class ModelResult:
    name: str
    path: Path
    added_columns: list[str]
    existed: bool
    has_star: bool
    unnamed: int
    error: str | None = None


def new_doc() -> CommentedMap:
    doc = CommentedMap()
    doc["version"] = 2
    doc["models"] = CommentedSeq()
    return doc


def _column_entry(name: str, placeholder: str) -> CommentedMap:
    col = CommentedMap()
    col["name"] = name
    col["description"] = placeholder
    return col


def _model_entry(name: str, columns: list[str], placeholder: str) -> CommentedMap:
    entry = CommentedMap()
    entry["name"] = name
    entry["description"] = placeholder
    cols = CommentedSeq()
    for col in columns:
        cols.append(_column_entry(col, placeholder))
    entry["columns"] = cols
    return entry


def _find_model(models: CommentedSeq, name: str) -> CommentedMap | None:
    for model in models:
        if isinstance(model, dict) and model.get("name") == name:
            return model
    return None


def merge_model(
    doc: CommentedMap,
    name: str,
    path: Path,
    extraction: ColumnExtraction,
    placeholder: str,
) -> ModelResult:
    """Merge one model's columns into ``doc`` in place, additively."""
    if extraction.error:
        return ModelResult(
            name=name,
            path=path,
            added_columns=[],
            existed=False,
            has_star=extraction.has_star,
            unnamed=extraction.unnamed,
            error=extraction.error,
        )

    doc.setdefault("version", 2)
    models = doc.setdefault("models", CommentedSeq())

    existing = _find_model(models, name)
    if existing is None:
        models.append(_model_entry(name, extraction.columns, placeholder))
        return ModelResult(
            name=name,
            path=path,
            added_columns=list(extraction.columns),
            existed=False,
            has_star=extraction.has_star,
            unnamed=extraction.unnamed,
        )

    # An existing model may have `columns:` present but empty (parsed as None);
    # normalize to a sequence before appending.
    existing_cols = existing.get("columns")
    if not isinstance(existing_cols, list):
        existing_cols = CommentedSeq()
        existing["columns"] = existing_cols
    known = {c.get("name") for c in existing_cols if isinstance(c, dict)}
    added: list[str] = []
    for col in extraction.columns:
        if col not in known:
            existing_cols.append(_column_entry(col, placeholder))
            added.append(col)
    return ModelResult(
        name=name,
        path=path,
        added_columns=added,
        existed=True,
        has_star=extraction.has_star,
        unnamed=extraction.unnamed,
    )


def generate_for_sql(
    doc: CommentedMap,
    path: Path,
    placeholder: str,
    dialect: str | None,
) -> ModelResult:
    """Extract columns from a single .sql model file and merge into ``doc``."""
    name = path.stem
    sql = path.read_text(encoding="utf-8")
    extraction = extract_columns(sql, dialect=dialect)
    return merge_model(doc, name, path, extraction, placeholder)
