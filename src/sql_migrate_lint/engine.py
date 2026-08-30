"""Ties the parser and rule registry together to lint a migration file's SQL text."""

from __future__ import annotations

from sql_migrate_lint.models import Finding, LintOptions
from sql_migrate_lint.parser import split_statements
from sql_migrate_lint.rules import ALL_RULES


def lint_sql(sql: str, filename: str, options: LintOptions) -> list[Finding]:
    """Lint raw SQL text and return all findings, sorted by line then rule id."""
    statements = split_statements(sql)
    findings: list[Finding] = []

    for rule in ALL_RULES:
        if rule.id in options.ignore:
            continue
        if rule.dialects and options.dialect not in rule.dialects:
            continue
        findings.extend(rule.check(statements, options, filename))

    findings.sort(key=lambda f: (f.line, f.rule_id))
    return findings
