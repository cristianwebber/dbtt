# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`dbtt` is a **batteries-included toolkit layered on top of dbt-core** — dbt stays
the transformation engine; dbtt adds the workflow commands dbt leaves out. It is
NOT a reimplementation of dbt and NOT a dbt distribution. When adding features,
prefer wrapping/reading dbt's own artifacts (project files, `profiles.yml`,
`manifest.json`) over reinventing them.

## Commands

Toolchain is [uv](https://docs.astral.sh/uv/). Common tasks:

```bash
uv sync                      # install deps + dev deps into .venv
uv run pytest                # full test suite
uv run pytest tests/test_lint.py::test_lint_reports_violations   # single test
uv run ruff check src tests  # lint
uv run dbtt --help           # run the CLI
uv build                     # build wheel/sdist (includes rules/*.sqlfluff data)
```

The published console script is `dbtt` → `dbtt.cli:main`.

## Architecture

`src/`-layout package `dbtt`. The CLI is Typer with a mix of command groups and
top-level verbs, assembled in `cli.py`:

- `dbtt yml generate` / `dbtt yml check` — group in `commands/yml.py`
- `dbtt lint` / `dbtt fix` — top-level verbs in `commands/lint.py`

**Core convention: one YAML file per model.** Each `<model>.sql` is documented
by a sibling `<model>.yml` holding exactly that model. `yml generate` writes
files this way (never a shared/combined file); `yml check` enforces it
(`core/model_docs.py`) and exits non-zero for CI.

`cli.py`'s root callback constructs one `Context` (`context.py`) per invocation
and stores it on `ctx.obj`. `Context.project` lazily discovers the surrounding
dbt project by walking up for `dbt_project.yml`. Commands pull shared state from
there rather than rediscovering it.

**`commands/` are thin** — argument parsing, Rich output, exit codes. All real
logic lives in **`core/`** so it is unit-testable without the CLI:

- `core/sql_columns.py` — extracts a model's output columns. `strip_jinja()`
  turns dbt SQL into parseable SQL (ref/source → identifiers, `config()`
  removed, other `{{ }}` → placeholder), then sqlglot reads the final SELECT's
  projection. Offline and best-effort: `SELECT *` and un-aliased expressions are
  reported (`has_star`, `unnamed`), never guessed.
- `core/schema_gen.py` — builds/merges dbt schema YAML. **Additive and
  non-destructive**: existing models, descriptions, tests, and column order are
  preserved; only missing models/columns are appended. This invariant is the
  point of the feature — keep it.
- `core/yaml_io.py` — ruamel round-trip load/dump. Always use this for schema
  files, never pyyaml, so comments and ordering survive.
- `core/dbt_project.py` — parse `dbt_project.yml` (name, `model-paths`,
  `profile`) and find the project root.
- `core/dbt_dialect.py` — map a dbt adapter to a sqlfluff dialect by reading
  `profiles.yml` (searched via `$DBT_PROFILES_DIR`, project root, `~/.dbt`).
- `core/sqlfluff_config.py` — decide which sqlfluff config governs a run and
  render the effective bundled config.
- `core/config.py` — dbtt's own `[tool.dbtt]` / `dbtt.toml` settings.

### Linting: config resolution (important, non-obvious)

`dbtt lint`/`fix` shell out to sqlfluff as `python -m sqlfluff` (so it runs from
dbtt's own venv) and pass its output straight through. Two layered decisions:

1. **Which ruleset.** If the project ships its own `.sqlfluff` (found walking up
   to the project root), dbtt **defers to it entirely** — it passes no `--config`
   and lets sqlfluff auto-discover, and `[tool.dbtt]` is ignored. Otherwise dbtt
   uses its **bundled** ruleset (`rules/default.sqlfluff`). The two are never
   merged.
2. **dbtt config overlay.** For the bundled case, `[tool.dbtt]` toggles
   (`commas`, `uppercase_keywords`) are overlaid onto the base `.sqlfluff` via
   `render_bundled_config()` and written to a temp file passed as `--config`.

The bundled ruleset intentionally has **no `dialect`** — it is supplied at
runtime: explicit `--dialect` > dbt-profile detection > hard error (exit 2). This
is what makes one ruleset work for every warehouse; do not hardcode a dialect
back into `rules/default.sqlfluff`.

## Conventions

- **Testing uses duckdb as an oracle.** Column extraction and `fix` output are
  cross-checked by *executing* SQL in duckdb (`duckdb_columns` fixture in
  `tests/conftest.py`) and comparing to dbtt's result, not just asserting
  hand-written expectations. Prefer this style for new SQL-parsing behavior.
- New behavior goes in `core/` with direct unit tests; keep `commands/` thin.
- Dependency version floors are deliberately **loose** (`sqlfluff>=3`, etc.) —
  don't tighten them without reason.
- Commit messages follow Conventional Commits (`feat(scope): …`). Do not `git
  push` unless explicitly asked; committing to `master` is fine when asked.
- Cross-session working notes are kept at `~/workspace/memory/dbtt.md`.
