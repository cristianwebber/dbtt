# dbtt

[![CI](https://github.com/cristianwebber/dbtt/actions/workflows/ci.yml/badge.svg)](https://github.com/cristianwebber/dbtt/actions/workflows/ci.yml)

A batteries-included toolkit that layers workflow helpers on top of
[dbt-core](https://github.com/dbt-labs/dbt-core). dbt stays the engine; `dbtt`
adds the ergonomic commands that dbt leaves out of the box.

## Install

```bash
uv sync          # dev
uv run dbtt --help
```

## Commands

dbtt enforces **one YAML file per model**: each `models/.../<model>.sql` is
documented by a sibling `<model>.yml` containing exactly that model. Small,
self-contained doc files are easier to review and to feed to LLMs than one big
shared schema file.

### `dbtt yml generate` — one schema YAML per model

Generates or refreshes a `<model>.yml` beside each model's `.sql` by statically
parsing the SQL and extracting output columns. Runs fully offline — no warehouse
connection required — using [sqlglot](https://github.com/tobymao/sqlglot).

```bash
dbtt yml generate models                     # write <model>.yml for each model
dbtt yml generate models/staging --dry-run   # preview without writing
```

Key properties:

- **One file per model.** `stg_orders.sql` → `stg_orders.yml`, next to it.
- **Non-destructive / additive.** Existing descriptions, tests, and column
  order are preserved; only missing models and columns are added.
- **Comment-preserving.** Uses `ruamel.yaml` round-tripping, so hand-written
  comments survive regeneration.
- **Honest about limits.** `SELECT *` and un-aliased expressions can't be
  resolved offline — they're reported as warnings rather than silently guessed.

### `dbtt yml check` — enforce one file per model

Verifies the convention and exits non-zero on any violation, so it can gate CI.

```bash
dbtt yml check models
```

Flags three problems: a YAML file documenting more than one model
(`multiple_models`), a single-model file not named after its model
(`misnamed`), and a model no YAML documents at all (`missing`). Sources/seed
files that declare no `models:` are ignored.

### `dbtt lint` / `dbtt fix` — SQL style enforcement

Lints and auto-fixes model SQL with [sqlfluff](https://sqlfluff.com), using an
opinionated bundled ruleset — **unless the project ships its own `.sqlfluff`,
in which case dbtt defers to it entirely** (the two are never merged).

```bash
dbtt lint models/            # report violations (read-only)
dbtt fix models/             # auto-fix in place
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

#### Configuring the house style

The two most-changed rules are exposed through a `[tool.dbtt]` table in your
`pyproject.toml` (or a standalone `dbtt.toml`) — standard TOML, no new format:

```toml
[tool.dbtt]
commas = "leading"          # or "trailing"
uppercase_keywords = true   # false -> lowercase keywords
```

For full control, add your own `.sqlfluff` to the project — dbtt then defers to
it entirely and `[tool.dbtt]` is ignored.

## Development

```bash
uv run pytest        # test suite (column extraction is cross-checked against duckdb)
uv run ruff check src tests
```
