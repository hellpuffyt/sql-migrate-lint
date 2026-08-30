"""Dialect-agnostic rules: irreversibility and data-loss hazards."""

from __future__ import annotations

import re

from sql_migrate_lint.models import Finding, LintOptions, Severity, Statement
from sql_migrate_lint.rules.base import (
    RE_DELETE,
    RE_DROP_TABLE,
    RE_TRUNCATE,
    RE_UPDATE,
    RE_WHERE,
    Rule,
    make_finding,
)

RE_DROP_COLUMN = re.compile(r"\bDROP\s+COLUMN\s+(?:IF\s+EXISTS\s+)?\S+", re.I)
RE_ALTER_TABLE_START = re.compile(r"^ALTER\s+TABLE\b", re.I)


def _drop_irreversible(
    statements: list[Statement], options: LintOptions, filename: str
) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in statements:
        text = stmt.normalized
        table_match = RE_DROP_TABLE.match(text)
        is_drop_column = RE_ALTER_TABLE_START.match(text) and RE_DROP_COLUMN.search(text)
        if not table_match and not is_drop_column:
            continue

        what = "table" if table_match else "column"
        findings.append(
            make_finding(
                RULE_DROP_IRREVERSIBLE,
                stmt,
                filename,
                message=(
                    f"DROP {what.upper()} is irreversible once committed: the data is "
                    "gone and there is no down migration that can restore it from the "
                    "database alone."
                ),
                lock_info=(
                    "ACCESS EXCLUSIVE lock (Postgres) / metadata lock (MySQL) while "
                    "dropped; brief, but the data loss is permanent."
                ),
                dialect="postgres, mysql",
                version_range="all supported versions",
                safe_rewrite=(
                    f"Take a verified backup or snapshot immediately before this "
                    f"migration runs, and record that backup's location in the "
                    f"migration's comments or PR description. Consider renaming the "
                    f"{what} instead and dropping it in a later release once you are "
                    "sure nothing depends on it."
                ),
            )
        )
    return findings


def _truncate(statements: list[Statement], options: LintOptions, filename: str) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in statements:
        if not RE_TRUNCATE.match(stmt.normalized):
            continue
        findings.append(
            make_finding(
                RULE_TRUNCATE,
                stmt,
                filename,
                message="TRUNCATE deletes all rows and is not recoverable without a backup.",
                lock_info=(
                    "ACCESS EXCLUSIVE lock (Postgres) / table lock (MySQL) for the "
                    "duration of the truncate."
                ),
                dialect="postgres, mysql",
                version_range="all supported versions",
                safe_rewrite=(
                    "Confirm this is intentional and that a backup exists. If only "
                    "some rows should go, use a `DELETE ... WHERE` in batches instead."
                ),
            )
        )
    return findings


def _update_delete_no_where(
    statements: list[Statement], options: LintOptions, filename: str
) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in statements:
        text = stmt.normalized
        is_update = RE_UPDATE.match(text) is not None
        is_delete = RE_DELETE.match(text) is not None
        if not (is_update or is_delete):
            continue
        if RE_WHERE.search(text):
            continue
        verb = "UPDATE" if is_update else "DELETE"
        findings.append(
            make_finding(
                RULE_UPDATE_DELETE_NO_WHERE,
                stmt,
                filename,
                message=(
                    f"{verb} without a WHERE clause affects every row in the table "
                    f"and cannot be undone without a backup."
                ),
                lock_info=(
                    "Row/table locks proportional to the full table for the duration "
                    "of the statement."
                ),
                dialect="postgres, mysql",
                version_range="all supported versions",
                safe_rewrite=(
                    f"Add a WHERE clause scoping the {verb.lower()} to the intended "
                    "rows, or if the intent really is every row, use TRUNCATE (for "
                    "DELETE) and document it as an explicit, backed-up decision."
                ),
            )
        )
    return findings


RULE_DROP_IRREVERSIBLE = Rule(
    id="GEN001",
    name="drop-irreversible",
    default_severity=Severity.WARNING,
    dialects=(),
    check=_drop_irreversible,
    description="DROP TABLE/COLUMN is irreversible without a backup.",
)
RULE_TRUNCATE = Rule(
    id="GEN002",
    name="truncate",
    default_severity=Severity.WARNING,
    dialects=(),
    check=_truncate,
    description="TRUNCATE is irreversible without a backup.",
)
RULE_UPDATE_DELETE_NO_WHERE = Rule(
    id="GEN003",
    name="update-delete-no-where",
    default_severity=Severity.ERROR,
    dialects=(),
    check=_update_delete_no_where,
    description="UPDATE/DELETE without WHERE affects the whole table.",
)

RULES: tuple[Rule, ...] = (
    RULE_DROP_IRREVERSIBLE,
    RULE_TRUNCATE,
    RULE_UPDATE_DELETE_NO_WHERE,
)
