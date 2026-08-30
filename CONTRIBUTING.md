# Contributing

Contributions are welcome. This project is deliberately small in scope: a
static linter for SQL migration locking/rewrite/irreversibility hazards. Bug
reports for false positives/negatives on real-world migrations are
especially useful.

## Development setup

```bash
git clone https://github.com/hellpuffyt/sql-migrate-lint.git
cd sql-migrate-lint
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

## Running the checks

```bash
pytest
ruff check .
mypy
```

All three must pass before a pull request will be merged.

## Adding a rule

1. Add the check function and `Rule` definition to the appropriate module in
   `src/sql_migrate_lint/rules/` (`postgres.py`, `mysql.py`, or
   `generic.py` for dialect-agnostic rules).
2. Register it in that module's `RULES` tuple.
3. Give it the next free rule ID in its family (`PG0xx`, `MY0xx`, `GEN0xx`).
4. Write tests covering both the rule firing and its safe counterpart *not*
   firing.
5. Add the rule to the table in `README.md`.
6. Add an example to `examples/migrations/dangerous/` (and, if there's a
   safe counterpart worth showing, to `examples/migrations/safe/`).

## Reporting a false positive or false negative

Please include the exact SQL statement, the dialect and target version you
ran with, and what you expected to happen. A minimal `.sql` snippet
reproducing the issue is the fastest path to a fix.

## Code style

- Format/lint with `ruff`; keep `mypy --strict` clean.
- Prefer small, pure rule functions: `(statements, options, filename) -> list[Finding]`.
- Every `Finding` should carry a real lock description and a real safe
  rewrite — vague findings are worse than no finding.
