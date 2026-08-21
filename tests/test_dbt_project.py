"""dbt project discovery tests."""

from __future__ import annotations

from dbtt.core.dbt_project import find_project


def test_find_project_walks_up(tmp_path):
    (tmp_path / "dbt_project.yml").write_text(
        "name: my_project\nmodel-paths: [\"models\"]\n"
    )
    nested = tmp_path / "models" / "staging"
    nested.mkdir(parents=True)

    project = find_project(nested)
    assert project is not None
    assert project.name == "my_project"
    assert project.root == tmp_path
    assert project.is_under_models(nested / "stg_x.sql")


def test_find_project_none_when_absent(tmp_path):
    assert find_project(tmp_path) is None


def test_model_paths_default(tmp_path):
    (tmp_path / "dbt_project.yml").write_text("name: p\n")
    project = find_project(tmp_path)
    assert project.model_paths == ["models"]
