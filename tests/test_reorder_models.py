import yaml
import os
from tempfile import NamedTemporaryFile
from utils.reorder_models import reorder_models_in_yml
from tempfile import TemporaryDirectory


def test_reorder_models_in_yml():
    input_file_path = "tests/files/_test_a.yml"
    output_file_path = "tests/files/_test_a_expected.yml"

    with open(input_file_path, "r") as input_file:
        input_content = input_file.read()

    with TemporaryDirectory() as temp_dir:
        temp_file_path = os.path.join(temp_dir, "temp_file.yml")

        with open(temp_file_path, "w") as temp_file:
            # write content to temp file
            temp_file.write(input_content)

        reorder_models_in_yml(temp_file_path)

        with open(temp_file_path, "r") as temp_file:
            content = temp_file.read()
            reordered_yml_data = yaml.safe_load(content)

    print(content)
    print(reordered_yml_data)

    assert reordered_yml_data["models"][0]["name"] == "model_a"
    assert reordered_yml_data["models"][1]["name"] == "model_b"
    assert reordered_yml_data["models"][2]["name"] == "model_c"

    with open(output_file_path, "r") as file:
        expected_content = file.read()

    assert content == expected_content


def test_reorder_models_in_dbt_yml_empty_file():
    with NamedTemporaryFile(delete=False, mode="w") as temp_file:
        temp_file_path = temp_file.name

    reorder_models_in_yml(temp_file_path)

    with open(temp_file_path, "r") as file:
        data = yaml.safe_load(file)

    assert data == {}

    os.remove(temp_file_path)
