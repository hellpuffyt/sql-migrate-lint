from __future__ import annotations

from sql_migrate_lint.engine import lint_sql
from sql_migrate_lint.models import Dialect, Finding, LintOptions


def lint(
    sql: str,
    *,
    dialect: str = Dialect.POSTGRES,
    target_version: str | None = None,
    ignore: frozenset[str] = frozenset(),
    filename: str = "migration.sql",
) -> list[Finding]:
    options = LintOptions(dialect=dialect, target_version=target_version, ignore=ignore)
    return lint_sql(sql, filename, options)


def rule_ids(findings: list[Finding]) -> set[str]:
    return {f.rule_id for f in findings}
