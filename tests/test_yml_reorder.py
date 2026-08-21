"""Model reordering, with a focus on comment/format preservation (ruamel)."""

from __future__ import annotations

from dbtt.core import yaml_io
from dbtt.core.yaml_reorder import reorder_models


def _roundtrip(tmp_path, text):
    path = tmp_path / "_models.yml"
    path.write_text(text)
    doc = yaml_io.load(path)
    changed = reorder_models(doc)
    yaml_io.dump(doc, path)
    return changed, path.read_text()


def _names(tmp_path, text):
    path = tmp_path / "s.yml"
    path.write_text(text)
    doc = yaml_io.load(path)
    reorder_models(doc)
    return [m["name"] for m in doc["models"]]


def test_reorders_alphabetically(tmp_path):
    assert _names(
        tmp_path,
        "version: 2\nmodels:\n  - name: c\n  - name: a\n  - name: b\n",
    ) == ["a", "b", "c"]


def test_already_sorted_returns_false(tmp_path):
    changed, _ = _roundtrip(
        tmp_path, "version: 2\nmodels:\n  - name: a\n  - name: b\n"
    )
    assert changed is False


def test_single_model_no_change(tmp_path):
    changed, _ = _roundtrip(tmp_path, "version: 2\nmodels:\n  - name: only\n")
    assert changed is False


def test_no_models_key_is_noop():
    doc = {"version": 2, "sources": [{"name": "x"}]}
    assert reorder_models(doc) is False


def test_inline_comment_follows_its_model(tmp_path):
    text = (
        "version: 2\n"
        "models:\n"
        "  - name: zebra  # the striped one\n"
        "    description: z\n"
        "  - name: apple\n"
        "    description: a\n"
    )
    changed, out = _roundtrip(tmp_path, text)
    assert changed is True
    # apple now comes first, and zebra keeps its inline comment.
    assert out.index("name: apple") < out.index("name: zebra")
    assert "name: zebra  # the striped one" in out


def test_standalone_comment_between_items_survives(tmp_path):
    text = (
        "version: 2\n"
        "models:\n"
        "  - name: zebra\n"
        "  # notes about apple\n"
        "  - name: apple\n"
    )
    changed, out = _roundtrip(tmp_path, text)
    assert changed is True
    assert "notes about apple" in out  # comment not lost during reorder


def test_top_level_comment_preserved(tmp_path):
    text = (
        "# schema for staging\n"
        "version: 2\n"
        "models:\n"
        "  - name: b\n"
        "  - name: a\n"
    )
    _, out = _roundtrip(tmp_path, text)
    assert "# schema for staging" in out


def test_model_without_name_sorts_last_stably(tmp_path):
    path = tmp_path / "s.yml"
    path.write_text(
        "version: 2\nmodels:\n  - name: b\n  - foo: bar\n  - name: a\n"
    )
    doc = yaml_io.load(path)
    reorder_models(doc)
    names = [m.get("name") for m in doc["models"]]
    assert names == ["a", "b", None]
