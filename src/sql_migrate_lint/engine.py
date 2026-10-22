"""Ties the parser and rule registry together to lint a migration file's SQL text."""

from __future__ import annotations

from dataclasses import replace

from sql_migrate_lint.models import Finding, LintOptions, Severity, Statement
from sql_migrate_lint.parser import split_statements
from sql_migrate_lint.rules import ALL_RULES
from sql_migrate_lint.rules.base import small_table_keys, tables_created_before, target_table

# Rules whose risk is a long lock or rewrite on a table that already holds
# data. They do not apply to a table created earlier in the same file (it is
# empty), and are softened for tables the user declares small.
TABLE_LOCK_RULE_IDS = frozenset({"PG001", "PG002", "PG004", "PG005", "PG006", "MY001"})


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

    findings = _apply_table_context(findings, statements, options)
    findings.sort(key=lambda f: (f.line, f.rule_id))
    return findings


def _apply_table_context(
    findings: list[Finding], statements: list[Statement], options: LintOptions
) -> list[Finding]:
    created = tables_created_before(statements)
    small = small_table_keys(options)
    by_location = {(s.line, s.text): s for s in statements}
    result: list[Finding] = []
    for finding in findings:
        stmt = by_location.get((finding.line, finding.statement))
        table = target_table(stmt.normalized) if stmt is not None else None
        if finding.rule_id not in TABLE_LOCK_RULE_IDS or stmt is None or table is None:
            result.append(finding)
            continue
        if table in created[stmt.index]:
            continue  # created earlier in this migration: empty, nothing to lock out
        if table in small:
            bound = (
                f" (declared under {options.rows_threshold} rows)"
                if options.rows_threshold is not None
                else ""
            )
            finding = replace(
                finding,
                severity=Severity.INFO,
                message=f"{finding.message} Softened to info: table listed in "
                f"--small-table{bound}.",
            )
        result.append(finding)
    return result
