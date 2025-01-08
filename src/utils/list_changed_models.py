import os
import subprocess


def list_changed_models(branch: str):
    """
    List changed dbt models in the project for a given branch.

    Args:
        branch (str): The branch to compare changes against.

    Returns:
        List[Tuple[str, str, str]]: A list of tuples containing the model name, status, and color.
    """

    modified_result = subprocess.run(
        ["git", "diff", "--name-only", branch],
        capture_output=True,
        text=True,
        check=True,
    )
    untracked_result = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
    )
    deleted_result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=D", branch],
        capture_output=True,
        text=True,
        check=True,
    )

    deleted_files = deleted_result.stdout.splitlines()
    modified_files = [
        file
        for file in modified_result.stdout.splitlines()
        if file not in deleted_files
    ]
    untracked_files = untracked_result.stdout.splitlines()

    models = []
    for file in modified_files:
        if file.endswith(".sql"):
            models.append(
                (os.path.splitext(os.path.basename(file))[0], "Modified", "yellow")
            )

    for file in untracked_files:
        if file.endswith(".sql"):
            models.append((os.path.splitext(os.path.basename(file))[0], "New", "green"))

    for file in deleted_files:
        if file.endswith(".sql"):
            models.append(
                (os.path.splitext(os.path.basename(file))[0], "Deleted", "red")
            )

    return models
