"""MySQL-specific lint rules."""

from __future__ import annotations

import re

from sql_migrate_lint.models import Dialect, Finding, LintOptions, Severity, Statement
from sql_migrate_lint.rules.base import RE_ALTER_TABLE, Rule, make_finding

RE_ALGORITHM_SAFE = re.compile(r"\bALGORITHM\s*=\s*(INPLACE|INSTANT)\b", re.I)
RE_LOCK_NONE = re.compile(r"\bLOCK\s*=\s*NONE\b", re.I)
RE_DDL_START = re.compile(r"^(CREATE|ALTER|DROP|TRUNCATE|RENAME)\b", re.I)
RE_BEGIN_TX = re.compile(r"^(START\s+TRANSACTION|BEGIN)\b", re.I)


def _alter_table_copy_behavior(
    statements: list[Statement], options: LintOptions, filename: str
) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in statements:
        text = stmt.normalized
        if not RE_ALTER_TABLE.match(text):
            continue
        if RE_ALGORITHM_SAFE.search(text):
            continue  # already opted into a safe, in-place algorithm

        target = options.target_major_version()
        version_note = (
            "on MySQL/MariaDB versions or storage engines that fall back to the "
            "COPY algorithm"
            if target is None
            else f"on the targeted MySQL {target}.x if the change is not INPLACE-eligible"
        )
        findings.append(
            make_finding(
                RULE_ALTER_TABLE_COPY,
                stmt,
                filename,
                message=(
                    f"ALTER TABLE without an explicit ALGORITHM clause may fall back "
                    f"to rebuilding the table via a full table copy {version_note}, "
                    "holding a lock for the whole rebuild."
                ),
                lock_info=(
                    "COPY algorithm: table-level lock blocking reads and writes for "
                    "the whole copy. INPLACE with LOCK=NONE: no exclusive lock, "
                    "concurrent DML allowed."
                ),
                dialect=Dialect.MYSQL,
                version_range="most severe before 8.0; INSTANT column add from 8.0.12",
                safe_rewrite=(
                    "Add `ALGORITHM=INPLACE, LOCK=NONE` explicitly so MySQL refuses "
                    "the migration (rather than silently falling back to COPY) if the "
                    "change isn't eligible. For simple column additions on 8.0.12+, "
                    "`ALGORITHM=INSTANT` avoids a rebuild entirely."
                ),
            )
        )
    return findings


def _implicit_commit_in_transaction(
    statements: list[Statement], options: LintOptions, filename: str
) -> list[Finding]:
    has_explicit_tx = any(RE_BEGIN_TX.match(s.normalized) for s in statements)
    if not has_explicit_tx:
        return []

    findings: list[Finding] = []
    for stmt in statements:
        if not RE_DDL_START.match(stmt.normalized):
            continue
        findings.append(
            make_finding(
                RULE_IMPLICIT_COMMIT,
                stmt,
                filename,
                message=(
                    "This file mixes an explicit transaction (START TRANSACTION/BEGIN) "
                    "with DDL. In MySQL, DDL statements cause an implicit COMMIT, so "
                    "earlier statements in this 'transaction' are already committed and "
                    "cannot be rolled back if a later statement fails."
                ),
                lock_info="N/A (this is about transactional atomicity, not a lock).",
                dialect=Dialect.MYSQL,
                version_range="all supported versions",
                safe_rewrite=(
                    "Split DML that must be atomic into its own transaction, separate "
                    "from DDL, or accept that each DDL statement is its own commit "
                    "point and design the migration to be safely re-runnable."
                ),
            )
        )
    return findings


RULE_ALTER_TABLE_COPY = Rule(
    id="MY001",
    name="alter-table-copy-behavior",
    default_severity=Severity.WARNING,
    dialects=(Dialect.MYSQL,),
    check=_alter_table_copy_behavior,
    description="ALTER TABLE may fall back to a full-table-copy rebuild.",
)
RULE_IMPLICIT_COMMIT = Rule(
    id="MY002",
    name="implicit-commit",
    default_severity=Severity.WARNING,
    dialects=(Dialect.MYSQL,),
    check=_implicit_commit_in_transaction,
    description="DDL inside an explicit transaction causes an implicit commit in MySQL.",
)

RULES: tuple[Rule, ...] = (
    RULE_ALTER_TABLE_COPY,
    RULE_IMPLICIT_COMMIT,
)
