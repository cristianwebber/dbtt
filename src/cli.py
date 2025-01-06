from typer import Typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import os
import subprocess
from typing import Optional

import typer
from typing_extensions import Annotated

app = Typer()
console = Console()


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


@app.command()
def list_changed(
    branch: Annotated[
        str,
        typer.Argument(
            help="The branch to compare changes against. Default is HEAD."
        ),
    ] = "HEAD",
):
    """List changed models not committed in the project."""

    if branch != "HEAD":
        result = subprocess.run(
            ["git", "branch", "--list", branch],
            capture_output=True,
            text=True,
            check=True,
        )
        if not result.stdout.strip():
            console.print(
                f"[bold red]Error:[/bold red] The branch '{branch}' does not exist.",
                style="red",
            )
            return

    models = list_changed_models(branch)
    table = Table(title="Changed dbt models")
    table.add_column("Model Name", style="cyan")
    table.add_column("Status", style="green")

    for model in models:
        table.add_row(model[0], model[1], style=model[2])

    console.print(table)


@app.command()
def greet(name: str):
    console.print(f"Hello, {name}!")


def main():
    app()


if __name__ == "__main__":
    main()
