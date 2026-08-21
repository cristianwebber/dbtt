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
