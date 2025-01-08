import yaml
import os
from tempfile import NamedTemporaryFile
from utils.reorder_models import reorder_models_in_yml


def test_reorder_models_in_yml():
    with NamedTemporaryFile(delete=False, mode="w") as temp_file:
        temp_file_path = temp_file.name
        temp_file.write("""
models:
  - name: model_b
  - name: model_c
  - name: model_a
""")

    reorder_models_in_yml(temp_file_path)

    with open(temp_file_path, "r") as file:
        data = yaml.safe_load(file)

    assert data["models"][0]["name"] == "model_a"
    assert data["models"][1]["name"] == "model_b"
    assert data["models"][2]["name"] == "model_c"

    with open(temp_file_path, "r") as file:
        content = file.read()

    expected_content = """
models:

- name: model_a

- name: model_b

- name: model_c
"""
    assert content.strip() == expected_content.strip()

    os.remove(temp_file_path)


def test_reorder_models_in_dbt_yml_empty_file():
    with NamedTemporaryFile(delete=False, mode="w") as temp_file:
        temp_file_path = temp_file.name

    reorder_models_in_yml(temp_file_path)

    with open(temp_file_path, "r") as file:
        data = yaml.safe_load(file)

    assert data == {}

    os.remove(temp_file_path)
