# sql-migrate-lint

Lint SQL migrations for operations that lock tables, rewrite data, or are
irreversible on a live database.

## What

`sql-migrate-lint` reads your `.sql` migration files and flags statements
that are safe in a code review and safe against a thousand-row staging
database, but dangerous against a production table with tens of millions of
rows: statements that take a strong lock, rewrite the table, or destroy data
with no way back. Every finding names the specific lock taken, what that
lock blocks, the affected dialect and version range, and a safe rewrite.

## Why

A migration that passes review and passes staging can still take production
down, because staging has a thousand rows and production has forty million.
`ALTER TABLE ... ADD COLUMN ... NOT NULL DEFAULT` rewrites the whole table
under an exclusive lock on PostgreSQL before version 11. `CREATE INDEX`
without `CONCURRENTLY` blocks writes for the duration of the build. Nothing
in the SQL text says so — the danger is in what the database engine does
with the statement, not in the statement's syntax. This tool encodes that
engine-level knowledge so it surfaces in code review, before the migration
ever reaches production.

## Features

- PostgreSQL and MySQL dialect awareness, including version-boundary rules
  (e.g. `ADD COLUMN ... NOT NULL DEFAULT` is safe from Postgres 11 onward).
- Every finding reports: rule ID, severity, line, the offending statement,
  the lock taken and what it blocks, the affected dialect/version range, and
  a safe rewrite.
- Detects irreversible operations: `DROP TABLE`/`DROP COLUMN`, `TRUNCATE`,
  and `UPDATE`/`DELETE` without a `WHERE` clause.
- Flags missing `lock_timeout`/`statement_timeout` guards on migrations that
  take a strong lock.
- Correct SQL tokenizing via `sqlparse`: a `--` inside a string literal is
  never mistaken for a comment, and keywords inside string literals never
  trigger false positives.
- Human text, JSON, and SARIF output, for terminals, scripts, and GitHub
  code scanning.
- Works on individual files or whole migration directories (numbered
  migration layouts like Flyway/Sqitch-style `NNN_description.sql`).

## Rules reference

| Rule | Severity | Dialect | What it catches | Lock taken / what it blocks | Safe rewrite |
|---|---|---|---|---|---|
| `PG001` add-column-not-null-default | warning/error | postgres | `ADD COLUMN ... NOT NULL DEFAULT` | ACCESS EXCLUSIVE for a full table rewrite (pre-11 only; metadata-only from 11) | Add nullable column, backfill in batches, then `SET NOT NULL` + separate default |
| `PG002` create-index-concurrently | error | postgres | `CREATE INDEX` without `CONCURRENTLY` | SHARE lock blocking writes for the build | `CREATE INDEX CONCURRENTLY` |
| `PG003` drop-index-concurrently | warning | postgres | `DROP INDEX` without `CONCURRENTLY` | ACCESS EXCLUSIVE, brief | `DROP INDEX CONCURRENTLY` |
| `PG004` alter-column-type | error | postgres | `ALTER COLUMN ... TYPE` (except `-> TEXT`) | ACCESS EXCLUSIVE for a full rewrite | Add column, backfill, swap; or accept if a documented no-op (e.g. widening `VARCHAR`) |
| `PG005` add-constraint-not-valid | error | postgres | `ADD CONSTRAINT ... FOREIGN KEY/CHECK` without `NOT VALID` | Full-table scan under lock | Add `NOT VALID`, then `VALIDATE CONSTRAINT` separately |
| `PG006` set-not-null | warning | postgres | `ALTER COLUMN ... SET NOT NULL` | ACCESS EXCLUSIVE for a full scan | Validated `CHECK (col IS NOT NULL)` first (PG 12+ skips the scan) |
| `PG007` rename-hazard | warning | postgres | `RENAME TO` / `RENAME COLUMN` | Brief ACCESS EXCLUSIVE, but breaks in-flight app code | Expand/contract deploy across two releases |
| `PG008` vacuum-cluster-reindex | error | postgres | `VACUUM FULL`, `CLUSTER`, `REINDEX` without `CONCURRENTLY` | ACCESS EXCLUSIVE for the whole rewrite | `pg_repack`, or `REINDEX CONCURRENTLY` (12+) |
| `PG009` missing-lock-timeout | warning | postgres | Strong-lock migration with no `lock_timeout`/`statement_timeout` | N/A — absence of a guard | Set `lock_timeout`/`statement_timeout` at the top of the migration |
| `MY001` alter-table-copy-behavior | warning | mysql | `ALTER TABLE` without `ALGORITHM=` | COPY algorithm locks the table for the whole rebuild | `ALGORITHM=INPLACE, LOCK=NONE`, or `ALGORITHM=INSTANT` (8.0.12+) |
| `MY002` implicit-commit | warning | mysql | DDL mixed with `START TRANSACTION`/`BEGIN` | N/A — DDL implicitly commits in MySQL | Keep DDL and atomic DML in separate migrations |
| `GEN001` drop-irreversible | warning | both | `DROP TABLE` / `DROP COLUMN` | Brief, but data loss is permanent | Verified backup first; consider a rename-then-drop-later pattern |
| `GEN002` truncate | warning | both | `TRUNCATE` | Table lock, permanent data loss | Confirm intent and backup; use scoped `DELETE` if partial |
| `GEN003` update-delete-no-where | error | both | `UPDATE`/`DELETE` with no `WHERE` | Locks proportional to the full table | Add a `WHERE` clause, or use `TRUNCATE` deliberately |

## Dialects

- **PostgreSQL** (`--dialect postgres`, default): the primary, most detailed
  dialect, including PostgreSQL-version-aware rules via `--target-version`.
- **MySQL** (`--dialect mysql`): covers pre-8.0 `ALTER TABLE` copy behavior,
  `ALGORITHM=INPLACE`/`LOCK=NONE`, and implicit-commit hazards.
- The irreversibility rules (`GEN00x`) apply regardless of dialect.

## Architecture

```
src/sql_migrate_lint/
  parser.py     statement splitting + normalization, built on sqlparse's
                token stream so comments and string literals never leak
                into keyword matching
  models.py     Statement, Finding, Severity, LintOptions
  rules/
    base.py       Rule dataclass + shared regex fragments
    postgres.py   PG001-PG009
    mysql.py      MY001-MY002
    generic.py    GEN001-GEN003 (dialect-agnostic)
  engine.py     runs the rule registry over parsed statements
  reporters.py  text / json / sarif renderers
  cli.py        argument parsing, file discovery, exit codes
```

Each rule is a pure function `(statements, options, filename) -> list[Finding]`
registered with metadata (id, name, default severity, applicable dialects).
The engine filters rules by dialect and `--ignore`, then sorts findings by
line number.

## Installation

```bash
pip install sql-migrate-lint
```

Or from source:

```bash
git clone https://github.com/hellpuffyt/sql-migrate-lint.git
cd sql-migrate-lint
pip install -e ".[dev]"
```

## Usage

```bash
sql-migrate-lint migrations/                       # lint a directory, postgres, warning+
sql-migrate-lint migrations/0007_add_email.sql \
  --dialect postgres --target-version 11+           # PG001 will not fire below
sql-migrate-lint migrations/ --dialect mysql
sql-migrate-lint migrations/ --format json
sql-migrate-lint migrations/ --format sarif --output results.sarif
sql-migrate-lint migrations/ --severity error        # only fail on error/critical
sql-migrate-lint migrations/ --ignore PG007,GEN001    # skip specific rules
```

Exit code is `0` if no finding meets or exceeds `--severity` (default:
`warning`), `1` if one does, and `2` on a usage error or unparsable file.

## Examples

`examples/migrations/safe/` and `examples/migrations/dangerous/` contain
runnable examples. Try:

```bash
sql-migrate-lint examples/migrations/dangerous/ --dialect postgres
sql-migrate-lint examples/migrations/safe/ --dialect postgres
```

The dangerous set exits non-zero; the safe set exits zero.

## Testing

```bash
pip install -e ".[dev]"
pytest
ruff check .
mypy
```

## Limitations

- This is a static linter: it reasons from the SQL text, not from your
  actual schema or row counts. `--rows-threshold`/`--small-table` let you
  document known-small tables, but the tool cannot verify table size itself.
- `ALTER COLUMN ... TYPE` safety depends on the *previous* column type,
  which isn't present in an `ALTER TABLE` statement; only the `-> TEXT`
  case is treated as a guaranteed no-op. Widening `VARCHAR(n)` is flagged
  even though it is often safe, because the linter can't see the old length.
  Verify manually before disabling `PG004` for such a statement.
- Multi-statement control flow (stored procedure bodies, `DO $$ ... $$`
  blocks) is treated as opaque text; statements inside such blocks are not
  individually analyzed.
- Rule coverage reflects common, well-documented locking behavior; it is not
  a substitute for reading your database's release notes on a major
  upgrade.

## Security

`sql-migrate-lint` only reads the files you point it at; it does not connect
to a database, execute SQL, or send data anywhere. Report security issues by
opening a GitHub issue.

## License

MIT. See [LICENSE](LICENSE).
