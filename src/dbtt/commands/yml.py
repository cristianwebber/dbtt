"""`dbtt yml` — schema (.yml) generation and maintenance commands."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from ruamel.yaml import YAML
from typing_extensions import Annotated

from ..core import schema_gen, yaml_io
from ..core.yaml_reorder import reorder_models

app = typer.Typer(help="Generate and maintain dbt schema YAML files.")
console = Console()

YAML_SUFFIXES = (".yml", ".yaml")


def _collect_sql_files(paths: list[Path]) -> list[Path]:
    """Expand files/directories into a sorted, de-duplicated list of .sql files."""
    found: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        candidates = sorted(path.rglob("*.sql")) if path.is_dir() else [path]
        for candidate in candidates:
            if candidate.suffix != ".sql":
                console.print(f"[yellow]skip[/yellow] {candidate} (not a .sql file)")
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                found.append(candidate)
    return found


def _collect_yml_files(paths: list[Path]) -> list[Path]:
    """Expand files/directories into a sorted, de-duplicated list of YAML files."""
    found: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path.is_dir():
            candidates = sorted(
                p for p in path.rglob("*") if p.suffix in YAML_SUFFIXES
            )
        else:
            candidates = [path]
        for candidate in candidates:
            if candidate.suffix not in YAML_SUFFIXES:
                console.print(f"[yellow]skip[/yellow] {candidate} (not a YAML file)")
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                found.append(candidate)
    return found


def _target_for(sql_file: Path, output: Optional[Path], filename: str) -> Path:
    if output is not None:
        return output
    return sql_file.parent / filename


def _dump_str(doc) -> str:
    buf = io.StringIO()
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = 4096
    yaml.dump(doc, buf)
    return buf.getvalue()


def _safe_load(path: Path) -> tuple[object, Optional[str]]:
    """Load YAML, returning (doc, None) or (None, error) instead of raising.

    Guards every command against a single malformed file crashing the run.
    """
    try:
        return yaml_io.load(path), None
    except Exception as err:  # ruamel raises several parser/scanner error types
        first_line = next((ln for ln in str(err).splitlines() if ln.strip()), "parse error")
        return None, first_line.strip()


@app.command()
def generate(
    paths: Annotated[
        Optional[list[Path]],
        typer.Argument(help="Model .sql files or directories. Defaults to the current directory."),
    ] = None,
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Write all models into this single schema file."),
    ] = None,
    filename: Annotated[
        str,
        typer.Option("--filename", help="Schema filename created per model directory when --output is not set."),
    ] = "_models.yml",
    placeholder: Annotated[
        str,
        typer.Option("--placeholder", help="Text used for new description fields."),
    ] = "",
    dialect: Annotated[
        Optional[str],
        typer.Option("--dialect", help="SQL dialect for the parser (e.g. duckdb, snowflake, bigquery)."),
    ] = None,
    write: Annotated[
        bool,
        typer.Option("--write/--dry-run", help="Apply changes (default). Use --dry-run to preview without writing."),
    ] = True,
) -> None:
    """Generate/refresh schema YAML from model SQL, preserving existing content."""
    sql_files = _collect_sql_files(paths or [Path(".")])
    if not sql_files:
        console.print("[bold red]Error:[/bold red] no .sql model files found.")
        raise typer.Exit(code=1)

    # Group models by the schema file they belong to so each existing file is
    # loaded once and merged into, never overwritten per-model.
    groups: dict[Path, list[Path]] = {}
    for sql_file in sql_files:
        groups.setdefault(_target_for(sql_file, output, filename), []).append(sql_file)

    table = Table(title="dbtt yml generate")
    table.add_column("Model", style="cyan")
    table.add_column("Schema file", style="magenta")
    table.add_column("Result", style="green")

    docs: dict[Path, object] = {}
    warnings: list[str] = []
    for target, files in groups.items():
        loaded: object = None
        if target.exists():
            loaded, error = _safe_load(target)
            if error is not None:
                table.add_row("—", target.name, f"[red]load error:[/red] {error}")
                continue  # never overwrite a file we couldn't read
            if loaded is not None and not isinstance(loaded, dict):
                table.add_row("—", target.name, "[red]skipped:[/red] not a schema mapping")
                continue  # never clobber unexpected content
        doc = loaded if isinstance(loaded, dict) else schema_gen.new_doc()
        docs[target] = doc

        for sql_file in files:
            result = schema_gen.generate_for_sql(doc, sql_file, placeholder, dialect)
            if result.error:
                table.add_row(result.name, target.name, f"[red]error:[/red] {result.error}")
                continue
            if result.existed and not result.added_columns:
                status = "up to date"
            elif result.existed:
                status = f"+{len(result.added_columns)} column(s)"
            else:
                status = f"new model, {len(result.added_columns)} column(s)"
            table.add_row(result.name, target.name, status)
            if result.has_star:
                warnings.append(f"{result.name}: SELECT * cannot be expanded offline; add columns manually.")
            if result.unnamed:
                warnings.append(f"{result.name}: {result.unnamed} unnamed expression(s) skipped; add aliases.")

    console.print(table)
    for warning in warnings:
        console.print(f"[yellow]warn[/yellow] {warning}")

    if write:
        for target, doc in docs.items():
            yaml_io.dump(doc, target)
        console.print(f"[bold green]Wrote[/bold green] {len(docs)} schema file(s).")
    else:
        console.print("[dim]Dry run — re-run with --write to save. Preview:[/dim]")
        for target, doc in docs.items():
            console.print(f"[magenta]# {target}[/magenta]")
            console.print(_dump_str(doc))


@app.command()
def fix(
    paths: Annotated[
        Optional[list[Path]],
        typer.Argument(help="Schema .yml files or directories. Defaults to the current directory."),
    ] = None,
    write: Annotated[
        bool,
        typer.Option("--write/--dry-run", help="Apply changes (default). Use --dry-run to preview without writing."),
    ] = True,
) -> None:
    """Alphabetically reorder the models in schema YAML files (comments preserved)."""
    yml_files = _collect_yml_files(paths or [Path(".")])
    if not yml_files:
        console.print("[bold red]Error:[/bold red] no YAML files found.")
        raise typer.Exit(code=1)

    table = Table(title="dbtt yml fix")
    table.add_column("File", style="cyan")
    table.add_column("Result", style="green")

    changed = 0
    for path in yml_files:
        doc, error = _safe_load(path)
        if error is not None:
            table.add_row(str(path), f"[red]load error:[/red] {error}")
            continue
        if not isinstance(doc, dict) or "models" not in doc:
            table.add_row(str(path), "[dim]skipped (no models)[/dim]")
            continue
        if reorder_models(doc):
            changed += 1
            table.add_row(str(path), "reordered" if write else "would reorder")
            if write:
                yaml_io.dump(doc, path)
        else:
            table.add_row(str(path), "[dim]already sorted[/dim]")

    console.print(table)
    if write:
        console.print(f"[bold green]Reordered[/bold green] {changed} file(s).")
    elif changed:
        console.print(f"[dim]{changed} file(s) would change — re-run with --write to apply.[/dim]")
