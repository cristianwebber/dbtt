"""sqlfluff config resolution: user .sqlfluff wins, else bundled defaults."""

from __future__ import annotations

from dbtt.core.config import DbttConfig
from dbtt.core.sqlfluff_config import (
    bundled_config_text,
    render_bundled_config,
    resolve_config,
)


def test_bundled_used_when_no_user_config(tmp_path):
    resolved = resolve_config(tmp_path, tmp_path)
    assert resolved.source == "bundled"


def test_user_config_takes_precedence(tmp_path):
    (tmp_path / ".sqlfluff").write_text("[sqlfluff]\ndialect = duckdb\n")
    resolved = resolve_config(tmp_path, tmp_path)
    assert resolved.source == "user"


def test_user_config_found_walking_up(tmp_path):
    (tmp_path / ".sqlfluff").write_text("[sqlfluff]\ndialect = duckdb\n")
    nested = tmp_path / "models" / "staging"
    nested.mkdir(parents=True)
    resolved = resolve_config(nested, tmp_path)
    assert resolved.source == "user"


def test_search_stops_at_project_root(tmp_path):
    # A .sqlfluff above the project root must NOT be picked up.
    (tmp_path / ".sqlfluff").write_text("[sqlfluff]\ndialect = duckdb\n")
    root = tmp_path / "project"
    root.mkdir()
    resolved = resolve_config(root, root)
    assert resolved.source == "bundled"


def test_bundled_config_has_no_dialect():
    # Dialect is supplied at runtime, never hardcoded in the ruleset.
    text = bundled_config_text()
    assert "line_position = leading" in text
    assert "dialect =" not in text


def test_render_is_valid_and_dialect_free():
    # The rendered effective config must remain dialect-free (supplied at runtime)
    # and carry the requested toggles.
    text = render_bundled_config(DbttConfig())
    assert "dialect" not in text
    assert "line_position = leading" in text
