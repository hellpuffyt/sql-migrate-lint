# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed (each verified against PostgreSQL 17 where it concerns server behaviour)

- `PG001` was silent on Postgres 11+ (and for nullable columns on any
  version) for `ADD COLUMN` with a volatile default, `serial`, identity or
  `STORED` generated column, all of which rewrite the table.
- `PG004` silently passed every `-> TEXT` change, but `CHAR(n) -> TEXT` and
  non-string types `-> TEXT` rewrite the table; it now warns (error with
  `USING`).
- `PG005` missed `ADD FOREIGN KEY` / `ADD CHECK` without a constraint name;
  its CHECK lock description said "briefly" although ACCESS EXCLUSIVE is
  held for the whole scan.
- `PG009` was satisfied by a `SET lock_timeout` placed *after* the DDL.
- `GEN001` missed `ALTER TABLE ... DROP name` without the `COLUMN` keyword.
- `GEN003` was suppressed by a `WHERE` inside a subquery.
- Lock rules fired as errors on tables created earlier in the same file.
- `--small-table` / `--rows-threshold` were accepted but had no effect.
- `--severity` did not filter the report as its help text says.
- A non-UTF-8 file crashed with a traceback (now exit code 2).
- Double-quoted identifiers were all masked to the same text.
- README claimed `pip install sql-migrate-lint`; the package is not on PyPI.

### Added

- Representative safe/dangerous migration corpus with exact expectations.
- Opt-in PostgreSQL ground-truth tests and a separate CI job for them.
- `SECURITY.md`, `.editorconfig`, `docs/PRODUCTION_READINESS.md`.

## [0.1.0] - 2026-08-30

### Added

- Initial release.
- PostgreSQL rules `PG001`-`PG009`: `ADD COLUMN ... NOT NULL DEFAULT`,
  `CREATE`/`DROP INDEX` without `CONCURRENTLY`, `ALTER COLUMN ... TYPE`,
  `ADD CONSTRAINT` without `NOT VALID`, `SET NOT NULL`, table/column rename
  hazards, `VACUUM FULL`/`CLUSTER`/`REINDEX` without `CONCURRENTLY`, and
  missing `lock_timeout`/`statement_timeout` guards.
- MySQL rules `MY001`-`MY002`: `ALTER TABLE` copy-algorithm fallback and
  implicit-commit-inside-transaction hazards.
- Dialect-agnostic rules `GEN001`-`GEN003`: irreversible `DROP`, `TRUNCATE`,
  and `UPDATE`/`DELETE` without `WHERE`.
- Text, JSON, and SARIF output formats.
- `--dialect`, `--target-version`, `--severity`, `--ignore`, and
  `--rows-threshold`/`--small-table` CLI options.
- Statement splitting built on `sqlparse`'s token stream, so comments and
  string literals never confuse rule matching.
