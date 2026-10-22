# Production readiness — sql-migrate-lint

Audit date: 2026-10-22. Tested code commit: `fe5ebe2` (branch
`audit/production-readiness`); later commits change documentation and
repository metadata only.

## Scope

Static linter for `.sql` migration files: splits statements with `sqlparse`
(comments and string literals masked), runs 14 rules (PG001–PG009,
MY001–MY002, GEN001–GEN003) and renders text / JSON / SARIF. It never
connects to a database. Architecture: `parser.py` → `rules/` → `engine.py`
(rule selection + table context) → `reporters.py` / `cli.py`.

## Platforms and prerequisites

Python ≥ 3.10, dependency `sqlparse` (0.6.0 tested). Verified on macOS 27
(Apple Silicon) with Python 3.12 (full + clean clone), 3.10 and 3.13 (test
suite). PostgreSQL ground truth verified against PostgreSQL 17.11 (Homebrew
binaries, throwaway `initdb` cluster, Unix socket only, never the brew
service). MySQL rules were **not** checked against a MySQL server (none
available). Linux/Windows CI legs not run for this audit.

## Clean-clone verification (README "from source" + Examples + Testing)

```bash
git clone -b audit/production-readiness <repo> sql-migrate-lint && cd sql-migrate-lint
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                                           # exit 0
pytest -q -rs                                                     # 135 passed, 19 skipped (PG opt-in)
ruff check .                                                      # exit 0
mypy                                                              # no issues in 12 files
sql-migrate-lint examples/migrations/dangerous/ --dialect postgres  # exit 1
sql-migrate-lint examples/migrations/safe/ --dialect postgres       # "No issues found.", exit 0
sql-migrate-lint examples/migrations/dangerous/ --format sarif --output ../x.sarif  # SARIF 2.1.0, 9 results
SQL_MIGRATE_LINT_PG_BINDIR=/opt/homebrew/opt/postgresql@17/bin pytest -rs tests/test_pg_ground_truth.py  # 19 passed
python -m build --wheel                                           # exit 0
```

## Commands and outcomes

| Step | Command | Exit | Result |
|---|---|---:|---|
| Baseline (main `243d52d`) | `pytest -q` | 0 | 94 passed, 0 failed, 0 skipped |
| Baseline lint/types/examples | `ruff check .`, `mypy`, examples | 0, 0, 1/0 | as documented |
| Final, portable | `pytest -q -rs` (3.10, 3.12, 3.13) | 0 | 135 passed, 0 failed, 19 skipped (each skip = PG ground truth not requested) |
| Final, with PostgreSQL 17.11 | `SQL_MIGRATE_LINT_PG_BINDIR=... pytest -q -rs` | 0 | 154 passed, 0 skipped |
| PG requested but binaries missing | `SQL_MIGRATE_LINT_PG_BINDIR=/nonexistent pytest tests/test_pg_ground_truth.py` | 1 | 19 errors (fails, never skips) |
| New tests on original code | `PYTHONPATH=<main>/src pytest tests/test_audit_regressions.py tests/test_corpus.py` | 1 | 29 failed, 12 passed |
| Ground truth on original code | same with PG | 1 | 12 failed, 7 passed |
| Dependency audit | `uvx pip-audit -r <frozen env> --disable-pip --no-deps --strict` | 0 | no known vulnerabilities |
| Secret scan (tree + all history) | detect-secrets + credential-pattern `git grep` | – | none |
| Stress | 3000-deep parentheses / 5000 statements / 200 kB identifier | – | clean `SqlParseError` (exit 2) / 3.6 s / 0.04 s |

CI: default branch `main`: **success** (run on `243d52d`). Audit branch:
pending until pushed. The new `pg-ground-truth` job (runner's preinstalled
PostgreSQL) has not run yet.

## PostgreSQL facts verified (PostgreSQL 17.11)

Table rewrite = `pg_relation_filenode` changes. Rewrites: `ADD COLUMN` with
`clock_timestamp()`, `gen_random_uuid()`, `random()`, `nextval()` defaults,
`bigserial`, identity, `STORED` generated; `char(5)→text`, `int→text`,
`int→bigint`. No rewrite: `NOT NULL DEFAULT 0`, `DEFAULT now()`,
`DEFAULT 'x'`, `varchar(10)→text`, `varchar(10)→varchar(20)`. Lock modes
(`pg_locks` inside a transaction): `CREATE INDEX` → ShareLock; `ADD CHECK`
→ AccessExclusiveLock; `ADD FOREIGN KEY` → ShareRowExclusiveLock on both
tables; `SET NOT NULL` → AccessExclusiveLock. All encoded in
`tests/test_pg_ground_truth.py`.

## Bugs found and fixed (regression tests in `tests/test_audit_regressions.py`, `tests/test_corpus.py`, `tests/test_pg_ground_truth.py`)

| # | Severity | Defect |
|---|---|---|
| 1 | High (false negative) | PG001 silent on 11+ for volatile defaults / serial / identity / stored generated columns, which rewrite the table (verified) |
| 2 | High (false negative) | PG004 silently passed every `-> TEXT`; `char→text`, `int→text` rewrite (verified). Now warning (error with `USING`). **Expected value of `test_pg004_clean_when_converting_to_text` changed, justification in the test.** |
| 3 | High (false negative) | PG005 missed `ADD FOREIGN KEY` / `ADD CHECK` without a constraint name |
| 4 | Medium (false negative) | PG009 satisfied by a timeout set *after* the DDL |
| 5 | Medium (false negative) | GEN003 suppressed by a `WHERE` inside a subquery |
| 6 | Medium (false negative) | GEN001 missed `DROP name` without `COLUMN` |
| 7 | Medium (false positive) | errors on indexes/constraints for a table created in the same file |
| 8 | Medium (dead flags) | `--small-table` / `--rows-threshold` accepted but ignored |
| 9 | Low | `--severity` did not filter the report (contrary to `--help`) |
| 10 | Low | non-UTF-8 file → traceback |
| 11 | Low | quoted identifiers all normalized to the same `"xxxx"` text |
| 12 | Low (docs) | PG005 lock text said CHECK lock is held "briefly"; README `pip install sql-migrate-lint` (not on PyPI) |

## Security review

The tool reads only the given paths (directories walked for `*.sql`) and
writes only `--output`; no network, no SQL execution, no deserialisation
beyond `sqlparse`. `sqlparse`'s grouping-depth limit turns pathological
nesting into a clean exit 2. CI token restricted to `contents: read`; the
new job's actions are pinned to commit SHAs resolved with `gh api`
(`actions/checkout` v4 `11d5960…`, `actions/setup-python` v5 `a26af69…`).
No secrets in tree or history; no rotation needed.

## Known limitations and risks

- Static analysis of SQL text only: no schema, no row counts; `DO $$…$$`
  and function bodies are opaque.
- Volatile-default detection covers well-known built-ins only.
- Widening `VARCHAR(n)` is still reported as an error (old length unknown).
- Schema qualification is ignored when matching "created in this file".
- MySQL rules unverified against a server.

## Acceptance checklist

| Item | Expected | Command / test | Result | Actual | Reference |
|---|---|---|---|---|---|
| A1 | Install from source, CLI on PATH | README | pass | exit 0 | clean clone |
| A2 | Lint/types/tests green | `ruff`, `mypy`, `pytest` | pass | 135 passed, 19 skipped | CI |
| A3 | Representative safe migrations clean (PG 17) | `tests/test_corpus.py` | pass | 4/4 clean, exit 0 | corpus/safe |
| A4 | Representative dangerous migrations flagged exactly | `tests/test_corpus.py` | pass | 6/6 exact, exit 1 | corpus/dangerous |
| A5 | Rewrite/lock claims match a real PostgreSQL | `tests/test_pg_ground_truth.py` | pass | 19/19 on 17.11 | ground truth |
| A6 | A rewriting statement never lints clean | same | pass | yes | `test_rewrite_behaviour_matches_linter` |
| A7 | Exit codes 0/1/2 as documented | tests | pass | yes | `tests/test_cli.py`, regressions |
| A8 | SARIF/JSON outputs valid | existing tests + clean clone | pass | SARIF 2.1.0 | `tests/test_reporters.py` |

## Classification proposal

**Partially Verified** — PostgreSQL rules verified against a real
PostgreSQL 17 server, corpus and clean clone pass on macOS. Not verified:
MySQL rules against a MySQL server; Linux/Windows CI legs and the new
PostgreSQL CI job (pending push); PostgreSQL versions other than 17.
