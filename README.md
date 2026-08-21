# dbtt

A batteries-included toolkit that layers workflow helpers on top of
[dbt-core](https://github.com/dbt-labs/dbt-core). dbt stays the engine; `dbtt`
adds the ergonomic commands that dbt leaves out of the box.

## Install

```bash
uv sync          # dev
uv run dbtt --help
```

## Commands

### `dbtt yml generate` — schema YAML from model SQL

Generates or refreshes dbt schema (`.yml`) files by statically parsing your
model SQL and extracting output columns. Runs fully offline — no warehouse
connection required — using [sqlglot](https://github.com/tobymao/sqlglot).

```bash
# Preview (dry run) for every model under models/staging
dbtt yml generate models/staging --dialect duckdb

# Write one _models.yml per model directory, merging into existing files
dbtt yml generate models --write --dialect duckdb

# Collapse everything into a single schema file
dbtt yml generate models -o models/schema.yml --write
```

Key properties:

- **Non-destructive / additive.** Existing descriptions, tests, and column
  order are preserved; only missing models and columns are added.
- **Comment-preserving.** Uses `ruamel.yaml` round-tripping, so hand-written
  comments survive regeneration.
- **Honest about limits.** `SELECT *` and un-aliased expressions can't be
  resolved offline — they're reported as warnings rather than silently guessed.

### `dbtt lint` / `dbtt fix` — SQL style enforcement

Lints and auto-fixes model SQL with [sqlfluff](https://sqlfluff.com), using an
opinionated bundled ruleset — **unless the project ships its own `.sqlfluff`,
in which case dbtt defers to it entirely** (the two are never merged).

```bash
dbtt lint models/            # report violations
dbtt fix models/             # auto-fix in place
dbtt fix models/ --check     # show what would change, write nothing
dbtt lint models/ --dialect bigquery   # override the dialect
```

The **dialect is auto-detected** from your dbt profile (`profiles.yml` adapter
`type`), so the same ruleset works for Snowflake, BigQuery, Postgres, DuckDB,
and more. Pass `--dialect` to override, or when there's no profile to read.

Bundled house style:

| Rule | Setting |
| --- | --- |
| Commas | leading |
| Keywords | UPPERCASE |
| Functions / types / literals | lowercase |
| Line length | 120 |
| Indentation | 4 spaces |
| Aliases | explicit `AS` (columns & tables) |
| Columns in joins | must be table-qualified |
| `GROUP BY` / `ORDER BY` | by column name, not position |

Override any of these by adding your own `.sqlfluff` to the project.

## Development

```bash
uv run pytest        # test suite (column extraction is cross-checked against duckdb)
uv run ruff check src tests
```
