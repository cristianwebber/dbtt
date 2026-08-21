"""Column extraction tests, cross-checked against real duckdb execution."""

from __future__ import annotations

import pytest

from dbtt.core.sql_columns import extract_columns, strip_jinja

# (query, setup_sql). Each query is validated two ways: duckdb runs it to get the
# ground-truth output columns, and dbtt extracts them statically. They must match.
CASES = [
    (
        "select id, name from customers",
        "create table customers as select 1 as id, 'a' as name",
    ),
    (
        "select id, upper(name) as name_upper, 1 + 1 as two from customers",
        "create table customers as select 1 as id, 'a' as name",
    ),
    (
        """
        with base as (select id, amount from orders)
        select id, sum(amount) as total from base group by id
        """,
        "create table orders as select 1 as id, 10 as amount",
    ),
    (
        "select o.id as order_id, c.name as customer_name "
        "from orders o join customers c on o.cid = c.id",
        "create table orders as select 1 as id, 1 as cid;"
        "create table customers as select 1 as id, 'a' as name",
    ),
    (
        "select id, amount from a union all select id, amount from b",
        "create table a as select 1 as id, 2 as amount;"
        "create table b as select 3 as id, 4 as amount",
    ),
    (
        "select o.id as order_id from orders o",
        "create table orders as select 1 as id",
    ),
]


@pytest.mark.parametrize("query,setup", CASES)
def test_extract_matches_duckdb(query, setup, duckdb_columns):
    expected = duckdb_columns(query, setup)
    result = extract_columns(query, dialect="duckdb")
    assert result.error is None
    assert result.columns == expected


def test_select_star_is_flagged():
    result = extract_columns("select * from customers", dialect="duckdb")
    assert result.has_star is True
    assert result.columns == []


def test_qualified_star_is_flagged():
    result = extract_columns("select t.* from orders as t", dialect="duckdb")
    assert result.has_star is True
    assert result.columns == []


def test_star_mixed_with_columns_flags_and_keeps_named():
    result = extract_columns("select id, t.* from orders as t", dialect="duckdb")
    assert result.has_star is True
    assert result.columns == ["id"]


def test_duplicate_output_names_are_deduped():
    # Two projections that resolve to the same name are collapsed once; schema
    # YAML can't carry two columns with the same name anyway.
    result = extract_columns("select id, id from orders", dialect="duckdb")
    assert result.columns == ["id"]


def test_unparseable_sql_reports_error():
    result = extract_columns("this is not sql ;;;", dialect="duckdb")
    assert result.error is not None
    assert result.columns == []


def test_unnamed_expression_is_counted():
    # A bare expression with no alias has no stable name.
    result = extract_columns("select id, amount * 2 from orders", dialect="duckdb")
    assert result.columns == ["id"]
    assert result.unnamed == 1


def test_strip_jinja_makes_dbt_sql_runnable(duckdb_columns):
    dbt_sql = """
    {{ config(materialized='table') }}
    -- a dbt model
    with src as (
        select * from {{ source('raw', 'customers') }}
    )
    select
        id,
        upper(name) as name_upper
    from {{ ref('stg_customers') }}
    {# trailing comment #}
    """
    cleaned = strip_jinja(dbt_sql)
    # ref('stg_customers') -> stg_customers ; source('raw','customers') -> raw__customers
    assert "stg_customers" in cleaned
    assert "raw__customers" in cleaned
    assert "{{" not in cleaned and "{%" not in cleaned and "{#" not in cleaned

    # The cleaned SQL should now be executable in duckdb once its table exists.
    setup = "create table stg_customers as select 1 as id, 'a' as name"
    expected = duckdb_columns(cleaned, setup)
    result = extract_columns(dbt_sql, dialect="duckdb")
    assert result.columns == expected == ["id", "name_upper"]
