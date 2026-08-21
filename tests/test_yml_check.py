"""Tests for the one-YAML-file-per-model enforcement (`dbtt yml check`)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from dbtt.cli import app
from dbtt.core.model_docs import MISNAMED, MISSING, MULTIPLE_MODELS, check

runner = CliRunner()


# --- unit tests for the pure rule engine ---------------------------------

def test_compliant_layout_has_no_violations():
    sql = [Path("models/stg_a.sql"), Path("models/stg_b.sql")]
    yml = {
        Path("models/stg_a.yml"): ["stg_a"],
        Path("models/stg_b.yml"): ["stg_b"],
    }
    assert check(sql, yml) == []


def test_multiple_models_in_one_file():
    sql = [Path("models/stg_a.sql"), Path("models/stg_b.sql")]
    yml = {Path("models/_models.yml"): ["stg_a", "stg_b"]}
    violations = check(sql, yml)
    kinds = {v.kind for v in violations}
    assert MULTIPLE_MODELS in kinds
    # Both models are documented (in the shared file), so they aren't "missing";
    # the shared-file violation is what must be fixed.
    assert not any(v.kind == MISSING for v in violations)


def test_misnamed_single_model_file():
    sql = [Path("models/stg_a.sql")]
    yml = {Path("models/schema.yml"): ["stg_a"]}
    violations = check(sql, yml)
    assert any(v.kind == MISNAMED for v in violations)


def test_missing_documentation():
    sql = [Path("models/stg_a.sql")]
    yml: dict[Path, list[str]] = {}
    violations = check(sql, yml)
    assert [v.kind for v in violations] == [MISSING]


# --- end-to-end CLI tests -------------------------------------------------

def _model(models, name, sql="select id from x", yml=None):
    models.mkdir(parents=True, exist_ok=True)
    (models / f"{name}.sql").write_text(sql)
    if yml is not None:
        (models / f"{name}.yml").write_text(yml)


def test_check_ok(tmp_path):
    models = tmp_path / "models"
    _model(models, "stg_a", yml="version: 2\nmodels:\n  - name: stg_a\n")
    result = runner.invoke(app, ["yml", "check", str(models)])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_check_flags_shared_file(tmp_path):
    models = tmp_path / "models"
    _model(models, "stg_a")
    _model(models, "stg_b")
    (models / "_models.yml").write_text(
        "version: 2\nmodels:\n  - name: stg_a\n  - name: stg_b\n"
    )
    result = runner.invoke(app, ["yml", "check", str(models)])
    assert result.exit_code == 1
    assert "multiple_models" in result.output


def test_check_flags_missing(tmp_path):
    models = tmp_path / "models"
    _model(models, "stg_a")  # no yml
    result = runner.invoke(app, ["yml", "check", str(models)])
    assert result.exit_code == 1
    assert "missing" in result.output


def test_check_reports_unreadable_yaml(tmp_path):
    models = tmp_path / "models"
    _model(models, "stg_a", yml="version: 2\nmodels:\n  - name: stg_a\n")
    (models / "broken.yml").write_text("foo: [1, 2\n")
    result = runner.invoke(app, ["yml", "check", str(models)])
    assert result.exit_code == 1
    assert "load error" in result.output


def test_check_ignores_sources_file(tmp_path):
    models = tmp_path / "models"
    _model(models, "stg_a", yml="version: 2\nmodels:\n  - name: stg_a\n")
    # A sources-only file declares no models and must not trip the check.
    (models / "_sources.yml").write_text("version: 2\nsources:\n  - name: raw\n")
    result = runner.invoke(app, ["yml", "check", str(models)])
    assert result.exit_code == 0
