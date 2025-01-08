import yaml


def reorder_models_in_yml(file_path):
    with open(file_path, "r") as file:
        data = yaml.safe_load(file) or {}

    if "models" in data:
        data["models"] = sorted(data["models"], key=lambda x: x["name"])

    with open(file_path, "w") as file:
        yaml.dump(data, file, sort_keys=False)

    # Add an extra empty line between models
    with open(file_path, "r") as file:
        lines = file.readlines()

    with open(file_path, "w") as file:
        for line in lines:
            if line.startswith("- name:"):
                file.write("\n")
            file.write(line)
