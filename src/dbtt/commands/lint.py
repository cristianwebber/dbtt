"""`dbtt lint` / `dbtt fix` — SQL linting & auto-fix, powered by sqlfluff.

dbtt does not reimplement linting; it wraps sqlfluff with an opinionated bundled
ruleset and steps aside when the project ships its own ``.sqlfluff``. sqlfluff is
invoked as ``python -m sqlfluff`` so it always runs from the same interpreter/venv
as dbtt, and its familiar output is passed straight through.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from typing_extensions import Annotated

from ..context import Context
from ..core.config import ConfigError, DbttConfig, load_config
from ..core.dbt_dialect import detect_dialect
from ..core.sqlfluff_config import ResolvedConfig, render_bundled_config, resolve_config

console = Console()


def _resolve(ctx: typer.Context) -> Context:
    obj = ctx.obj
    return obj if isinstance(obj, Context) else Context()


def _config_for(app_ctx: Context) -> ResolvedConfig:
    project = app_ctx.project
    root = project.root if project else None
    return resolve_config(app_ctx.cwd, root)


def _load_dbtt_config(app_ctx: Context) -> DbttConfig:
    root = app_ctx.project.root if app_ctx.project else None
    try:
        return load_config(app_ctx.cwd, root)
    except ConfigError as err:
        console.print(f"[bold red]Config error:[/bold red] {err}")
        raise typer.Exit(code=2)


def _announce(resolved: ResolvedConfig, config: DbttConfig) -> None:
    if resolved.source == "user":
        console.print("[dim]Using project's own .sqlfluff ([tool.dbtt] ignored)[/dim]")
        return
    origin = f" ({config.source})" if config.source else " (defaults)"
    console.print(
        f"[dim]Using dbtt's bundled ruleset{origin}: "
        f"commas={config.commas}, uppercase_keywords={config.uppercase_keywords}[/dim]"
    )


def _resolve_dialect(app_ctx: Context, explicit: Optional[str]) -> tuple[Optional[str], str]:
    """Resolve the dialect: explicit flag > dbt profile detection > none."""
    if explicit:
        return explicit, "flag"
    if app_ctx.project:
        detected = detect_dialect(app_ctx.project)
        if detected:
            return detected, "dbt profile"
    return None, "none"


def _dialect_for_run(app_ctx: Context, resolved: ResolvedConfig, explicit: Optional[str]) -> Optional[str]:
    """Decide the dialect to pass to sqlfluff, or exit with guidance.

    With a user .sqlfluff we only override when a flag is given (their config
    sets its own dialect). With the bundled ruleset a dialect is mandatory, so
    if none can be resolved we stop with an actionable message.
    """
    dialect, source = _resolve_dialect(app_ctx, explicit)
    if resolved.source == "user":
        return dialect  # None unless explicitly overridden
    if dialect is None:
        console.print(
            "[bold red]Error:[/bold red] could not determine the SQL dialect.\n"
            "Pass [cyan]--dialect <name>[/cyan] (e.g. snowflake, bigquery, postgres, duckdb),\n"
            "or set a [cyan]profile:[/cyan] in dbt_project.yml with a matching profiles.yml."
        )
        raise typer.Exit(code=2)
    if source == "dbt profile":
        console.print(f"[dim]Detected dialect '{dialect}' from dbt profile[/dim]")
    return dialect


def _run_sqlfluff(
    subcommand: str,
    paths: list[Path],
    config_path: Optional[Path],
    dialect: Optional[str],
    extra: list[str],
) -> int:
    cmd = [sys.executable, "-m", "sqlfluff", subcommand]
    if config_path is not None:
        cmd += ["--config", str(config_path)]
    if dialect:
        cmd += ["--dialect", dialect]
    cmd += extra
    cmd += [str(p) for p in paths]
    completed = subprocess.run(cmd)
    return completed.returncode


def _execute(
    subcommand: str,
    resolved: ResolvedConfig,
    config: DbttConfig,
    paths: list[Path],
    dialect: Optional[str],
    extra: list[str],
) -> int:
    """Run sqlfluff, materializing the effective bundled config when applicable."""
    if resolved.source == "user":
        # The project's own .sqlfluff governs; sqlfluff auto-discovers it.
        return _run_sqlfluff(subcommand, paths, None, dialect, extra)
    # Render the bundled ruleset with the user's [tool.dbtt] toggles applied.
    with tempfile.TemporaryDirectory() as tmp:
        effective = Path(tmp) / "effective.sqlfluff"
        effective.write_text(render_bundled_config(config), encoding="utf-8")
        return _run_sqlfluff(subcommand, paths, effective, dialect, extra)


def lint(
    ctx: typer.Context,
    paths: Annotated[
        Optional[list[Path]],
        typer.Argument(help="Files or directories to lint. Defaults to the current directory."),
    ] = None,
    dialect: Annotated[
        Optional[str],
        typer.Option("--dialect", help="Override the SQL dialect."),
    ] = None,
) -> None:
    """Lint SQL models and report style violations without changing files."""
    app_ctx = _resolve(ctx)
    resolved = _config_for(app_ctx)
    config = _load_dbtt_config(app_ctx)
    _announce(resolved, config)
    run_dialect = _dialect_for_run(app_ctx, resolved, dialect)
    code = _execute("lint", resolved, config, paths or [Path(".")], run_dialect, [])
    raise typer.Exit(code=code)


def fix(
    ctx: typer.Context,
    paths: Annotated[
        Optional[list[Path]],
        typer.Argument(help="Files or directories to fix. Defaults to the current directory."),
    ] = None,
    dialect: Annotated[
        Optional[str],
        typer.Option("--dialect", help="Override the SQL dialect."),
    ] = None,
    check: Annotated[
        bool,
        typer.Option("--check", help="Report what would change without writing files."),
    ] = False,
) -> None:
    """Auto-fix SQL models in place (leading commas, casing, aliasing, ...)."""
    app_ctx = _resolve(ctx)
    resolved = _config_for(app_ctx)
    config = _load_dbtt_config(app_ctx)
    _announce(resolved, config)
    run_dialect = _dialect_for_run(app_ctx, resolved, dialect)
    extra = ["--check"] if check else []
    code = _execute("fix", resolved, config, paths or [Path(".")], run_dialect, extra)
    raise typer.Exit(code=code)
