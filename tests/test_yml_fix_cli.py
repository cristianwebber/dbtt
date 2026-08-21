"""End-to-end tests for `dbtt yml fix`."""

from __future__ import annotations

from typer.testing import CliRunner

from dbtt.cli import app

runner = CliRunner()

UNSORTED = "version: 2\nmodels:\n  - name: c\n  - name: a\n  - name: b\n"


def _schema(models_dir, name="_models.yml", text=UNSORTED):
    models_dir.mkdir(parents=True, exist_ok=True)
    path = models_dir / name
    path.write_text(text)
    return path


def test_fix_reorders_in_place(tmp_path):
    schema = _schema(tmp_path / "models")
    result = runner.invoke(app, ["yml", "fix", str(schema), "--write"])
    assert result.exit_code == 0, result.output

    lines = [ln.strip() for ln in schema.read_text().splitlines() if "name:" in ln]
    assert lines == ["- name: a", "- name: b", "- name: c"]


def test_fix_applies_by_default(tmp_path):
    # No flag -> changes are written.
    schema = _schema(tmp_path / "models")
    result = runner.invoke(app, ["yml", "fix", str(schema)])
    assert result.exit_code == 0
    lines = [ln.strip() for ln in schema.read_text().splitlines() if "name:" in ln]
    assert lines == ["- name: a", "- name: b", "- name: c"]


def test_fix_dry_run_writes_nothing(tmp_path):
    schema = _schema(tmp_path / "models")
    result = runner.invoke(app, ["yml", "fix", str(schema), "--dry-run"])
    assert result.exit_code == 0
    assert schema.read_text() == UNSORTED
    assert "would reorder" in result.output


def test_fix_is_idempotent(tmp_path):
    schema = _schema(tmp_path / "models")
    runner.invoke(app, ["yml", "fix", str(schema), "--write"])
    result = runner.invoke(app, ["yml", "fix", str(schema), "--write"])
    assert "already sorted" in result.output


def test_fix_directory_skips_non_schema_yaml(tmp_path):
    models = tmp_path / "models"
    _schema(models)
    # A YAML file with no models: (e.g. a sources file) must be left alone.
    (models / "_sources.yml").write_text("version: 2\nsources:\n  - name: raw\n")

    result = runner.invoke(app, ["yml", "fix", str(models), "--write"])
    assert result.exit_code == 0
    assert "skipped (no models)" in result.output


def test_fix_preserves_comments_through_cli(tmp_path):
    text = (
        "version: 2\n"
        "models:\n"
        "  - name: zebra  # striped\n"
        "  - name: apple\n"
    )
    schema = _schema(tmp_path / "models", text=text)
    runner.invoke(app, ["yml", "fix", str(schema), "--write"])
    out = schema.read_text()
    assert out.index("name: apple") < out.index("name: zebra")
    assert "# striped" in out


def test_fix_no_yaml_files_errors(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(app, ["yml", "fix", str(empty)])
    assert result.exit_code == 1
