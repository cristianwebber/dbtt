"""End-to-end CLI tests for `dbtt yaml generate`."""

from __future__ import annotations

from typer.testing import CliRunner

from dbtt.cli import app
from dbtt.core import yaml_io

runner = CliRunner()


def _make_model(models_dir, name, sql):
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / f"{name}.sql").write_text(sql)


def test_generate_writes_schema_file(tmp_path):
    models = tmp_path / "models" / "staging"
    _make_model(models, "stg_orders", "select id, amount from {{ ref('raw_orders') }}")

    result = runner.invoke(
        app, ["yml", "generate", str(models), "--write", "--dialect", "duckdb"]
    )
    assert result.exit_code == 0, result.output

    out = models / "_models.yml"
    assert out.exists()
    doc = yaml_io.load(out)
    assert doc["models"][0]["name"] == "stg_orders"
    assert [c["name"] for c in doc["models"][0]["columns"]] == ["id", "amount"]


def test_generate_dry_run_writes_nothing(tmp_path):
    models = tmp_path / "models"
    _make_model(models, "m", "select id from {{ ref('src') }}")

    result = runner.invoke(app, ["yml", "generate", str(models), "--dialect", "duckdb"])
    assert result.exit_code == 0
    assert not (models / "_models.yml").exists()
    assert "id" in result.output  # preview printed


def test_generate_is_idempotent_and_preserves_comments(tmp_path):
    models = tmp_path / "models"
    _make_model(models, "m", "select id from {{ ref('src') }}")
    out = models / "_models.yml"

    runner.invoke(app, ["yml", "generate", str(models), "--write", "--dialect", "duckdb"])
    # Simulate a human adding a comment + description.
    text = out.read_text().replace(
        "name: m\n", "name: m  # core model\n"
    )
    out.write_text(text)

    # Regenerate: nothing new, comment must survive.
    result = runner.invoke(
        app, ["yml", "generate", str(models), "--write", "--dialect", "duckdb"]
    )
    assert result.exit_code == 0
    assert "# core model" in out.read_text()


def test_generate_output_file_groups_all_models(tmp_path):
    models = tmp_path / "models"
    _make_model(models, "a", "select id from {{ ref('x') }}")
    _make_model(models, "b", "select id from {{ ref('y') }}")
    combined = tmp_path / "schema.yml"

    result = runner.invoke(
        app,
        ["yml", "generate", str(models), "-o", str(combined), "--write", "--dialect", "duckdb"],
    )
    assert result.exit_code == 0
    doc = yaml_io.load(combined)
    names = sorted(m["name"] for m in doc["models"])
    assert names == ["a", "b"]


def test_generate_no_models_errors(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(app, ["yml", "generate", str(empty)])
    assert result.exit_code == 1
