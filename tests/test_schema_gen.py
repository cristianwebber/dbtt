"""Schema generation & merge behavior tests."""

from __future__ import annotations

from pathlib import Path

from dbtt.core import schema_gen, yaml_io
from dbtt.core.sql_columns import ColumnExtraction


def _extraction(cols, **kw):
    return ColumnExtraction(columns=list(cols), **kw)


def test_new_model_added_with_columns():
    doc = schema_gen.new_doc()
    result = schema_gen.merge_model(
        doc, "stg_orders", Path("stg_orders.sql"), _extraction(["id", "amount"]), ""
    )
    assert result.existed is False
    assert result.added_columns == ["id", "amount"]
    model = doc["models"][0]
    assert model["name"] == "stg_orders"
    assert [c["name"] for c in model["columns"]] == ["id", "amount"]


def test_merge_is_additive_and_preserves_descriptions():
    doc = schema_gen.new_doc()
    schema_gen.merge_model(doc, "stg_orders", Path("x.sql"), _extraction(["id"]), "")
    # A human edits the description...
    doc["models"][0]["description"] = "Orders staging"
    doc["models"][0]["columns"][0]["description"] = "Primary key"

    # ...then a new column appears in the SQL and we regenerate.
    result = schema_gen.merge_model(
        doc, "stg_orders", Path("x.sql"), _extraction(["id", "amount"]), ""
    )
    assert result.existed is True
    assert result.added_columns == ["amount"]

    model = doc["models"][0]
    assert model["description"] == "Orders staging"
    assert model["columns"][0]["description"] == "Primary key"  # untouched
    assert [c["name"] for c in model["columns"]] == ["id", "amount"]


def test_merge_idempotent_reports_up_to_date():
    doc = schema_gen.new_doc()
    schema_gen.merge_model(doc, "m", Path("m.sql"), _extraction(["a", "b"]), "")
    result = schema_gen.merge_model(doc, "m", Path("m.sql"), _extraction(["a", "b"]), "")
    assert result.existed is True
    assert result.added_columns == []


def test_error_extraction_reports_error():
    doc = schema_gen.new_doc()
    result = schema_gen.merge_model(
        doc, "m", Path("m.sql"), ColumnExtraction(error="boom"), ""
    )
    assert result.error == "boom"
    assert doc["models"] == []


def test_merge_into_model_with_empty_columns_key(tmp_path):
    # A schema file where a model has `columns:` present but empty parses the
    # value as None; merging must not crash and should populate it.
    path = tmp_path / "_models.yml"
    path.write_text("version: 2\nmodels:\n  - name: m\n    columns:\n")
    doc = yaml_io.load(path)
    result = schema_gen.merge_model(
        doc, "m", Path("m.sql"), _extraction(["id", "amount"]), ""
    )
    assert result.existed is True
    assert result.added_columns == ["id", "amount"]
    assert [c["name"] for c in doc["models"][0]["columns"]] == ["id", "amount"]


def test_generate_for_sql_reads_file_and_survives_roundtrip(tmp_path):
    sql = tmp_path / "stg_customers.sql"
    sql.write_text(
        "select id, upper(name) as name_upper from {{ ref('raw_customers') }}"
    )
    doc = schema_gen.new_doc()
    result = schema_gen.generate_for_sql(doc, sql, placeholder="", dialect="duckdb")
    assert result.added_columns == ["id", "name_upper"]

    # Round-trip through ruamel to confirm the generated structure is valid YAML.
    out = tmp_path / "_models.yml"
    yaml_io.dump(doc, out)
    reloaded = yaml_io.load(out)
    assert reloaded["models"][0]["name"] == "stg_customers"
    assert [c["name"] for c in reloaded["models"][0]["columns"]] == ["id", "name_upper"]
