"""Static extraction of output columns from a dbt SQL model.

dbt's own ``codegen`` package infers columns by running the compiled query
against the warehouse and reading the result schema. That is the most accurate
approach but requires a live connection. For a fast, offline "batteries
included" experience we instead parse the SQL statically with sqlglot.

The two hard parts are (1) making Jinja-laced dbt SQL parseable and (2) reading
the output columns of the final ``SELECT``. This module owns both.

Limitations (surfaced to the caller, never guessed around):
  * ``SELECT *`` / ``t.*`` cannot be expanded without a warehouse schema.
  * Un-aliased complex expressions have no stable name and are skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp


@dataclass
class ColumnExtraction:
    columns: list[str] = field(default_factory=list)
    has_star: bool = False
    unnamed: int = 0
    error: str | None = None


# {{ ref('model') }} or {{ ref('package', 'model') }} -> last identifier
_REF_RE = re.compile(r"\{\{-?\s*ref\(\s*([^)]*?)\s*\)\s*-?\}\}")
# {{ source('src', 'table') }} -> src__table
_SOURCE_RE = re.compile(r"\{\{-?\s*source\(\s*([^)]*?)\s*\)\s*-?\}\}")
# {% ... %} control blocks and {# ... #} comments
_STMT_RE = re.compile(r"\{%-?.*?-?%\}", re.DOTALL)
_COMMENT_RE = re.compile(r"\{#.*?#\}", re.DOTALL)
# {{ config(...) }} is a statement-level call that yields no value; drop it whole
# rather than leaving a placeholder that would be invalid standalone SQL.
_CONFIG_RE = re.compile(r"\{\{-?\s*config\(.*?\)\s*-?\}\}", re.DOTALL)
# any remaining {{ ... }} expression (var(), macros, ...) sits in value position
_EXPR_RE = re.compile(r"\{\{-?.*?-?\}\}", re.DOTALL)

_QUOTED = re.compile(r"""['"]([^'"]*)['"]""")


def _args(raw: str) -> list[str]:
    return _QUOTED.findall(raw)


def _sanitize_identifier(name: str) -> str:
    cleaned = re.sub(r"\W", "_", name).strip("_")
    return cleaned or "unknown"


def strip_jinja(sql: str) -> str:
    """Replace dbt Jinja with placeholders so sqlglot can parse the query.

    ``ref``/``source`` become plausible table identifiers so that the shape of
    the query (and therefore its output columns) is preserved; everything else
    Jinja-related is removed.
    """

    def ref_sub(m: re.Match[str]) -> str:
        parts = _args(m.group(1))
        return _sanitize_identifier(parts[-1]) if parts else "ref_model"

    def source_sub(m: re.Match[str]) -> str:
        parts = _args(m.group(1))
        return _sanitize_identifier("__".join(parts)) if parts else "source_table"

    sql = _COMMENT_RE.sub("", sql)
    sql = _CONFIG_RE.sub("", sql)
    sql = _REF_RE.sub(ref_sub, sql)
    sql = _SOURCE_RE.sub(source_sub, sql)
    sql = _STMT_RE.sub("", sql)
    sql = _EXPR_RE.sub("_jinja_", sql)
    return sql


def extract_columns(sql: str, dialect: str | None = None) -> ColumnExtraction:
    """Return the output column names of a dbt model's final SELECT."""
    cleaned = strip_jinja(sql).strip()
    if not cleaned:
        return ColumnExtraction(error="empty query after removing Jinja")

    try:
        statement = sqlglot.parse_one(cleaned, dialect=dialect)
    except Exception as err:  # sqlglot raises many parse error subtypes
        return ColumnExtraction(error=f"could not parse SQL: {err}")

    select = statement.find(exp.Select) if not isinstance(statement, exp.Select) else statement
    # For a top-level SELECT sqlglot keeps CTEs on the same node, so this is the
    # final projection. find() would otherwise dive into a CTE's inner select.
    if isinstance(statement, exp.Select):
        select = statement
    if select is None:
        return ColumnExtraction(error="no SELECT statement found")

    result = ColumnExtraction()
    for projection in select.expressions:
        if isinstance(projection, exp.Star) or (
            isinstance(projection, exp.Column) and isinstance(projection.this, exp.Star)
        ):
            result.has_star = True
            continue
        name = projection.alias_or_name
        if name and name != "*":
            if name not in result.columns:
                result.columns.append(name)
        else:
            result.unnamed += 1
    return result
