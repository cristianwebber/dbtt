"""End-to-end tests for `dbtt lint` / `dbtt fix` (drive real sqlfluff)."""

from __future__ import annotations

from typer.testing import CliRunner

from dbtt.cli import app
from dbtt.core.sql_columns import strip_jinja

runner = CliRunner()

MESSY = """select id,
       amount,
       upper(status) as status
from {{ ref('orders') }}
"""


def _duckdb_project(tmp_path, adapter="duckdb", model_sql=MESSY):
    (tmp_path / "dbt_project.yml").write_text(
        "name: demo\nprofile: demo\nmodel-paths: [\"models\"]\n"
    )
    (tmp_path / "profiles.yml").write_text(
        f"demo:\n  target: dev\n  outputs:\n    dev:\n      type: {adapter}\n"
    )
    models = tmp_path / "models"
    models.mkdir()
    (models / "bad.sql").write_text(model_sql)
    return models / "bad.sql"


def test_fix_applies_bundled_rules_with_detected_dialect(tmp_path, monkeypatch, duckdb_columns):
    model = _duckdb_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["fix", "models/bad.sql"])
    assert result.exit_code == 0, result.output

    fixed = model.read_text()
    assert fixed.startswith("SELECT")           # keyword upcased
    assert "\n    , amount" in fixed            # leading comma + 4-space indent
    assert "upper(status) AS status" in fixed   # function lower, AS explicit

    # The fixed SQL must still be valid/executable — validate against duckdb.
    setup = "create table orders as select 1 as id, 2 as amount, 'x' as status"
    cols = duckdb_columns(strip_jinja(fixed), setup)
    assert cols == ["id", "amount", "status"]


def test_lint_reports_violations(tmp_path, monkeypatch):
    _duckdb_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["lint", "models/bad.sql"])
    assert result.exit_code != 0  # violations present
    assert "bundled ruleset" in result.output


def test_missing_dialect_errors_with_guidance(tmp_path, monkeypatch):
    # dbt project with no profile and no --dialect -> can't pick a dialect.
    (tmp_path / "dbt_project.yml").write_text("name: demo\n")
    models = tmp_path / "models"
    models.mkdir()
    (models / "m.sql").write_text("select 1 as id\n")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["lint", "models/m.sql"])
    assert result.exit_code == 2
    assert "could not determine the SQL dialect" in result.output


def test_explicit_dialect_flag_overrides(tmp_path, monkeypatch):
    (tmp_path / "dbt_project.yml").write_text("name: demo\n")
    models = tmp_path / "models"
    models.mkdir()
    (models / "clean.sql").write_text("SELECT 1 AS id\n")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["lint", "models/clean.sql", "--dialect", "duckdb"])
    assert result.exit_code == 0, result.output


def test_config_switches_to_trailing_commas(tmp_path, monkeypatch):
    # With commas=trailing + lowercase keywords, a lowercase trailing-comma model
    # should now be accepted where the defaults would have rejected it.
    _duckdb_project(tmp_path)
    (tmp_path / "dbtt.toml").write_text(
        "commas = \"trailing\"\nuppercase_keywords = false\n"
    )
    clean = tmp_path / "models" / "clean.sql"
    clean.write_text("select\n    id,\n    amount\nfrom {{ ref('orders') }}\n")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["lint", "models/clean.sql"])
    assert "commas=trailing" in result.output
    assert result.exit_code == 0, result.output


def test_leading_default_rejects_trailing_commas(tmp_path, monkeypatch):
    # Same file, no config -> defaults (leading) -> trailing commas are flagged.
    _duckdb_project(tmp_path)
    clean = tmp_path / "models" / "clean.sql"
    clean.write_text("SELECT\n    id,\n    amount\nFROM {{ ref('orders') }}\n")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["lint", "models/clean.sql"])
    assert result.exit_code != 0  # trailing commas rejected under leading default
    assert "commas=leading" in result.output


def test_invalid_config_reports_error(tmp_path, monkeypatch):
    _duckdb_project(tmp_path)
    (tmp_path / "dbtt.toml").write_text("commas = \"diagonal\"\n")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["lint", "models/bad.sql"])
    assert result.exit_code == 2
    assert "Config error" in result.output


def test_user_sqlfluff_is_respected(tmp_path, monkeypatch):
    model = _duckdb_project(tmp_path)
    # Project ships its own config -> dbtt must defer to it, not the bundled one.
    (tmp_path / ".sqlfluff").write_text(
        "[sqlfluff]\ndialect = duckdb\ntemplater = jinja\n\n"
        "[sqlfluff:templater:jinja]\napply_dbt_builtins = true\n"
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["lint", "models/bad.sql"])
    assert "project's own .sqlfluff" in result.output
    _ = model  # linting outcome depends on user's rules; we only assert config choice
