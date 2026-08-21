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

from ..core import model_docs, schema_gen, yaml_io

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


def _target_for(sql_file: Path) -> Path:
    # One YAML file per model, named after the model, beside its .sql.
    return sql_file.with_suffix(".yml")


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
    """Generate/refresh one YAML file per model from its SQL, preserving existing content."""
    sql_files = _collect_sql_files(paths or [Path(".")])
    if not sql_files:
        console.print("[bold red]Error:[/bold red] no .sql model files found.")
        raise typer.Exit(code=1)

    # Group models by the schema file they belong to so each existing file is
    # loaded once and merged into, never overwritten per-model.
    groups: dict[Path, list[Path]] = {}
    for sql_file in sql_files:
        groups.setdefault(_target_for(sql_file), []).append(sql_file)

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


def _models_declared_in(path: Path) -> tuple[list[str], Optional[str]]:
    """Return (model names declared in the YAML file, error)."""
    doc, error = _safe_load(path)
    if error is not None:
        return [], error
    if not isinstance(doc, dict):
        return [], None
    models = doc.get("models")
    if not isinstance(models, list):
        return [], None
    return [m["name"] for m in models if isinstance(m, dict) and m.get("name")], None


@app.command()
def check(
    paths: Annotated[
        Optional[list[Path]],
        typer.Argument(help="Model directories or files. Defaults to the current directory."),
    ] = None,
) -> None:
    """Enforce one YAML file per model (each <model>.sql needs a sibling <model>.yml)."""
    search = paths or [Path(".")]
    sql_files = [p.resolve() for p in _collect_sql_files(search)]
    yml_files = _collect_yml_files(search)

    yml_models: dict[Path, list[str]] = {}
    load_errors = 0
    for path in yml_files:
        names, error = _models_declared_in(path)
        if error is not None:
            console.print(f"[red]load error[/red] {path}: {error}")
            load_errors += 1
            continue
        if names:
            yml_models[path.resolve()] = names

    violations = model_docs.check(sql_files, yml_models)

    if not violations and not load_errors:
        console.print(
            f"[bold green]OK[/bold green] — {len(sql_files)} model(s), one YAML file each."
        )
        return

    table = Table(title="dbtt yml check")
    table.add_column("File", style="cyan")
    table.add_column("Problem", style="red")
    table.add_column("Detail", style="yellow")
    for v in violations:
        table.add_row(str(v.path), v.kind, v.message)
    console.print(table)
    console.print(
        f"[bold red]{len(violations)} violation(s)[/bold red]"
        + (f", {load_errors} unreadable file(s)" if load_errors else "")
        + "."
    )
    raise typer.Exit(code=1)
