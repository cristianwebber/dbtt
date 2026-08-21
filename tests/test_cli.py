"""End-to-end CLI tests for `dbtt yml generate`."""

from __future__ import annotations

from typer.testing import CliRunner

from dbtt.cli import app
from dbtt.core import yaml_io

runner = CliRunner()


def _make_model(models_dir, name, sql):
    models_dir.mkdir(parents=True, exist_ok=True)
    (models_dir / f"{name}.sql").write_text(sql)


def test_generate_writes_one_yaml_per_model(tmp_path):
    models = tmp_path / "models" / "staging"
    _make_model(models, "stg_orders", "select id, amount from {{ ref('raw_orders') }}")

    result = runner.invoke(
        app, ["yml", "generate", str(models), "--write", "--dialect", "duckdb"]
    )
    assert result.exit_code == 0, result.output

    out = models / "stg_orders.yml"  # named after the model
    assert out.exists()
    doc = yaml_io.load(out)
    assert doc["models"][0]["name"] == "stg_orders"
    assert [c["name"] for c in doc["models"][0]["columns"]] == ["id", "amount"]


def test_generate_applies_by_default(tmp_path):
    # No flag -> the schema file is written.
    models = tmp_path / "models"
    _make_model(models, "m", "select id from {{ ref('src') }}")
    result = runner.invoke(app, ["yml", "generate", str(models), "--dialect", "duckdb"])
    assert result.exit_code == 0
    assert (models / "m.yml").exists()


def test_generate_dry_run_writes_nothing(tmp_path):
    models = tmp_path / "models"
    _make_model(models, "m", "select id from {{ ref('src') }}")

    result = runner.invoke(app, ["yml", "generate", str(models), "--dry-run", "--dialect", "duckdb"])
    assert result.exit_code == 0
    assert not (models / "m.yml").exists()
    assert "id" in result.output  # preview printed


def test_generate_is_idempotent_and_preserves_comments(tmp_path):
    models = tmp_path / "models"
    _make_model(models, "m", "select id from {{ ref('src') }}")
    out = models / "m.yml"

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


def test_generate_writes_one_file_per_model_across_dirs(tmp_path):
    _make_model(tmp_path / "models" / "staging", "stg_a", "select id from {{ ref('x') }}")
    _make_model(tmp_path / "models" / "marts", "fct_b", "select id from {{ ref('y') }}")

    result = runner.invoke(app, ["yml", "generate", str(tmp_path / "models"), "--dialect", "duckdb"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "models" / "staging" / "stg_a.yml").exists()
    assert (tmp_path / "models" / "marts" / "fct_b.yml").exists()


def test_generate_merges_preserving_descriptions(tmp_path):
    models = tmp_path / "models"
    _make_model(models, "m", "select id from {{ ref('src') }}")
    out = models / "m.yml"

    runner.invoke(app, ["yml", "generate", str(models), "--dialect", "duckdb"])
    # A human documents the model and column...
    doc = yaml_io.load(out)
    doc["models"][0]["description"] = "My model"
    doc["models"][0]["columns"][0]["description"] = "The id"
    yaml_io.dump(doc, out)

    # ...then a new column appears and we regenerate.
    (models / "m.sql").write_text("select id, amount from {{ ref('src') }}")
    result = runner.invoke(app, ["yml", "generate", str(models), "--dialect", "duckdb"])
    assert result.exit_code == 0

    doc = yaml_io.load(out)
    model = doc["models"][0]
    assert model["description"] == "My model"          # preserved
    assert model["columns"][0]["description"] == "The id"  # preserved
    assert [c["name"] for c in model["columns"]] == ["id", "amount"]  # amount added


def test_generate_reports_select_star_warning(tmp_path):
    models = tmp_path / "models"
    _make_model(models, "m", "select * from {{ ref('src') }}")
    result = runner.invoke(app, ["yml", "generate", str(models), "--dry-run", "--dialect", "duckdb"])
    assert result.exit_code == 0
    assert "SELECT *" in result.output


def test_generate_does_not_clobber_unreadable_target(tmp_path):
    models = tmp_path / "models"
    _make_model(models, "m", "select id from {{ ref('x') }}")
    bad = models / "m.yml"
    bad.write_text("foo: [1, 2\n")  # malformed YAML

    result = runner.invoke(app, ["yml", "generate", str(models), "--dialect", "duckdb"])
    assert result.exit_code == 0
    assert "load error" in result.output
    assert bad.read_text() == "foo: [1, 2\n"  # left untouched


def test_generate_skips_non_mapping_target(tmp_path):
    models = tmp_path / "models"
    _make_model(models, "m", "select id from {{ ref('x') }}")
    target = models / "m.yml"
    target.write_text("- a\n- b\n")  # valid YAML, but a list not a mapping

    result = runner.invoke(app, ["yml", "generate", str(models), "--dialect", "duckdb"])
    assert "not a schema mapping" in result.output
    assert target.read_text() == "- a\n- b\n"  # not clobbered


def test_generate_no_models_errors(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(app, ["yml", "generate", str(empty)])
    assert result.exit_code == 1


def test_generated_layout_passes_check(tmp_path):
    # Generation output should satisfy the one-file-per-model check.
    models = tmp_path / "models"
    _make_model(models, "stg_a", "select id from {{ ref('x') }}")
    _make_model(models, "stg_b", "select id from {{ ref('y') }}")
    runner.invoke(app, ["yml", "generate", str(models), "--dialect", "duckdb"])

    result = runner.invoke(app, ["yml", "check", str(models)])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
