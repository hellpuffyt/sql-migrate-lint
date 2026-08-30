# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
