"""dbtt config loading (TOML) and its effect on the rendered ruleset."""

from __future__ import annotations

import configparser

import pytest

from dbtt.core.config import ConfigError, DbttConfig, load_config
from dbtt.core.sqlfluff_config import render_bundled_config


def test_defaults_when_no_config(tmp_path):
    config = load_config(tmp_path, tmp_path)
    assert config.commas == "leading"
    assert config.uppercase_keywords is True
    assert config.source is None


def test_pyproject_tool_table(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.dbtt]\ncommas = \"trailing\"\nuppercase_keywords = false\n"
    )
    config = load_config(tmp_path, tmp_path)
    assert config.commas == "trailing"
    assert config.uppercase_keywords is False
    assert config.source.name == "pyproject.toml"


def test_standalone_dbtt_toml(tmp_path):
    (tmp_path / "dbtt.toml").write_text("commas = \"trailing\"\n")
    config = load_config(tmp_path, tmp_path)
    assert config.commas == "trailing"
    assert config.source.name == "dbtt.toml"


def test_standalone_wins_over_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.dbtt]\ncommas = \"leading\"\n")
    (tmp_path / "dbtt.toml").write_text("commas = \"trailing\"\n")
    config = load_config(tmp_path, tmp_path)
    assert config.commas == "trailing"
    assert config.source.name == "dbtt.toml"


def test_pyproject_without_tool_table_is_ignored(tmp_path):
    # A pyproject with no [tool.dbtt] must not shadow defaults or a parent config.
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"x\"\n")
    config = load_config(tmp_path, tmp_path)
    assert config.source is None
    assert config.commas == "leading"


def test_config_found_walking_up(tmp_path):
    (tmp_path / "dbtt.toml").write_text("commas = \"trailing\"\n")
    nested = tmp_path / "models" / "staging"
    nested.mkdir(parents=True)
    config = load_config(nested, tmp_path)
    assert config.commas == "trailing"


def test_invalid_commas_raises(tmp_path):
    (tmp_path / "dbtt.toml").write_text("commas = \"sideways\"\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path, tmp_path)


def test_invalid_uppercase_raises(tmp_path):
    (tmp_path / "dbtt.toml").write_text("uppercase_keywords = \"yes\"\n")
    with pytest.raises(ConfigError):
        load_config(tmp_path, tmp_path)


def _read_rendered(config: DbttConfig) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(render_bundled_config(config))
    return parser


def test_render_applies_leading_upper_defaults():
    parser = _read_rendered(DbttConfig())
    assert parser["sqlfluff:layout:type:comma"]["line_position"] == "leading"
    assert parser["sqlfluff:rules:capitalisation.keywords"]["capitalisation_policy"] == "upper"


def test_render_applies_trailing_lower():
    parser = _read_rendered(DbttConfig(commas="trailing", uppercase_keywords=False))
    assert parser["sqlfluff:layout:type:comma"]["line_position"] == "trailing"
    assert parser["sqlfluff:rules:capitalisation.keywords"]["capitalisation_policy"] == "lower"
    # Untouched rules from the base survive.
    assert parser["sqlfluff"]["max_line_length"] == "120"
