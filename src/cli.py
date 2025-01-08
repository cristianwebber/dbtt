from typer import Typer
from rich.console import Console
from rich.table import Table
import os
import subprocess
from typing import Optional

import typer
from typing_extensions import Annotated
from utils.list_changed_models import list_changed_models
from utils.reorder_models import reorder_models_in_yml

app = Typer()
console = Console()


@app.command()
def list_changed(
    branch: Annotated[
        str,
        typer.Argument(help="The branch to compare changes against. Default is HEAD."),
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
def yml_fix(
    path: Annotated[
        Optional[str],
        typer.Argument(
            help="The path to the .yml file. If not provided, all .yml files in the current directory starting with '_' will be processed."
        ),
    ] = None,
):
    if not path:
        yml_files = [
            os.path.join(root, file)
            for root, _, files in os.walk(".")
            for file in files
            if file.endswith(".yml") and file.startswith("_")
        ]
        if not yml_files:
            console.print(
                "[bold red]Error:[/bold red] No valid .yml files found.", style="red"
            )
            return
        for yml_file in yml_files:
            reorder_models_in_yml(yml_file)
            console.print(f"[bold green]Reordered models in:[/bold green] {yml_file}")
    else:
        if not os.path.isfile(path):
            console.print(
                f"[bold red]Error:[/bold red] The file '{path}' does not exist.",
                style="red",
            )
            return
        if not path.endswith(".yml"):
            console.print(
                f"[bold red]Error:[/bold red] The file '{path}' is not a .yml file.",
                style="red",
            )
            return
        reorder_models_in_yml(path)
        console.print(f"[bold green]Reordered models in:[/bold green] {path}")


def main():
    app()


if __name__ == "__main__":
    main()
