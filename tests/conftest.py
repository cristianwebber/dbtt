"""Shared test helpers, including a duckdb-backed column oracle.

We validate dbtt's *static* column extraction against the columns a real engine
(duckdb) reports when it actually runs the query. That keeps the parser honest:
if duckdb and dbtt disagree on the output columns of a query, the test fails.
"""

from __future__ import annotations

import duckdb
import pytest


@pytest.fixture
def duckdb_columns():
    """Return a helper: (query, setup_sql) -> list of output column names."""

    def _columns(query: str, setup_sql: str = "") -> list[str]:
        con = duckdb.connect(":memory:")
        try:
            if setup_sql:
                con.execute(setup_sql)
            return list(con.sql(query).columns)
        finally:
            con.close()

    return _columns
