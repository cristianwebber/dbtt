"""dbtt command-line entrypoint.

Subcommands are organized into groups (``dbtt yaml …``, and more to come) so the
toolkit scales past a handful of commands.
"""

from __future__ import annotations

import typer

from . import __version__
from .commands import yml as yml_cmd

app = typer.Typer(
    help="dbtt — a batteries-included toolkit layered on top of dbt-core.",
    no_args_is_help=True,
)
app.add_typer(yml_cmd.app, name="yml")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"dbtt {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
) -> None:
    pass


def main() -> None:
    app()


if __name__ == "__main__":
    main()
