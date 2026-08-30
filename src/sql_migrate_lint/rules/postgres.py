"""PostgreSQL-specific lint rules."""

from __future__ import annotations

import re

from sql_migrate_lint.models import Dialect, Finding, LintOptions, Severity, Statement
from sql_migrate_lint.rules.base import (
    RE_ALTER_TABLE,
    RE_CLUSTER,
    RE_CONCURRENTLY,
    RE_CREATE_INDEX,
    RE_DROP_INDEX,
    RE_REINDEX,
    RE_SET_TIMEOUT,
    RE_VACUUM_FULL,
    Rule,
    make_finding,
)

_NON_COLUMN_ADD_KEYWORDS = r"CONSTRAINT|PRIMARY|UNIQUE|FOREIGN|CHECK|EXCLUDE"
RE_ADD_COLUMN = re.compile(
    rf"\bADD\s+(?:COLUMN\s+)?(?!(?:{_NON_COLUMN_ADD_KEYWORDS})\b)\S+", re.I
)
RE_NOT_NULL = re.compile(r"\bNOT\s+NULL\b", re.I)
RE_DEFAULT = re.compile(r"\bDEFAULT\b", re.I)
RE_ALTER_COLUMN_TYPE = re.compile(r"\bALTER\s+COLUMN\s+\S+\s+(?:SET\s+DATA\s+)?TYPE\s+(\S+)", re.I)
RE_TYPE_IS_TEXT = re.compile(r"^TEXT\b", re.I)
RE_ADD_CONSTRAINT_FK_CHECK = re.compile(
    r"\bADD\s+CONSTRAINT\s+\S+\s+(FOREIGN\s+KEY|CHECK)\b", re.I
)
RE_NOT_VALID = re.compile(r"\bNOT\s+VALID\b", re.I)
RE_SET_NOT_NULL = re.compile(r"\bALTER\s+COLUMN\s+\S+\s+SET\s+NOT\s+NULL\b", re.I)
RE_RENAME_TABLE = re.compile(r"\bRENAME\s+TO\s+\S+", re.I)
RE_RENAME_COLUMN = re.compile(r"\bRENAME\s+(?:COLUMN\s+)?\S+\s+TO\s+\S+", re.I)

STRONG_LOCK_PG_RULE_IDS = {
    "PG002",
    "PG003",
    "PG004",
    "PG005",
    "PG006",
    "PG008",
    "PG001",
}


def _add_column_not_null_default(
    statements: list[Statement], options: LintOptions, filename: str
) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in statements:
        text = stmt.normalized
        if not RE_ALTER_TABLE.match(text):
            continue
        if not RE_ADD_COLUMN.search(text):
            continue
        if not (RE_NOT_NULL.search(text) and RE_DEFAULT.search(text)):
            continue

        target = options.target_major_version()
        if target is not None and target >= 11:
            continue  # safe: PG 11+ performs this as a metadata-only change

        severity = Severity.ERROR if target is not None else Severity.WARNING
        note = (
            "before this table's target Postgres."
            if target is not None
            else "on Postgres < 11 (no --target-version given; assuming the worst case)."
        )
        findings.append(
            make_finding(
                RULE_ADD_COLUMN_NOT_NULL_DEFAULT,
                stmt,
                filename,
                message=(
                    "ADD COLUMN ... NOT NULL DEFAULT rewrites the entire table "
                    f"{note} From Postgres 11 onward this is a fast, metadata-only "
                    "change and this rule will not fire with --target-version 11 or higher."
                ),
                lock_info=(
                    "ACCESS EXCLUSIVE lock for the duration of the table rewrite; "
                    "blocks all reads and writes on the table."
                ),
                dialect=Dialect.POSTGRES,
                version_range="< 11 (safe from 11 onward)",
                safe_rewrite=(
                    "On Postgres 11+ this is already safe. On older versions: add the "
                    "column nullable with no default, backfill in batches, then add the "
                    "NOT NULL constraint via `SET NOT NULL` (or a validated CHECK) and "
                    "set the default separately."
                ),
                severity=severity,
            )
        )
    return findings


def _create_index_no_concurrently(
    statements: list[Statement], options: LintOptions, filename: str
) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in statements:
        text = stmt.normalized
        if not RE_CREATE_INDEX.match(text):
            continue
        if RE_CONCURRENTLY.search(text):
            continue
        findings.append(
            make_finding(
                RULE_CREATE_INDEX_CONCURRENTLY,
                stmt,
                filename,
                message="CREATE INDEX without CONCURRENTLY blocks writes on the table.",
                lock_info=(
                    "SHARE lock, which blocks INSERT/UPDATE/DELETE for the duration "
                    "of the index build."
                ),
                dialect=Dialect.POSTGRES,
                version_range="all supported versions",
                safe_rewrite=(
                    "Use `CREATE INDEX CONCURRENTLY` (must run outside an explicit "
                    "transaction block; cannot be combined with other DDL in the same "
                    "statement)."
                ),
            )
        )
    return findings


def _drop_index_no_concurrently(
    statements: list[Statement], options: LintOptions, filename: str
) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in statements:
        text = stmt.normalized
        if not RE_DROP_INDEX.match(text):
            continue
        if RE_CONCURRENTLY.search(text):
            continue
        findings.append(
            make_finding(
                RULE_DROP_INDEX_CONCURRENTLY,
                stmt,
                filename,
                message="DROP INDEX without CONCURRENTLY briefly blocks queries using the index.",
                lock_info=(
                    "ACCESS EXCLUSIVE lock while dropping; brief but can queue behind "
                    "or block concurrent readers/writers."
                ),
                dialect=Dialect.POSTGRES,
                version_range="all supported versions",
                safe_rewrite="Use `DROP INDEX CONCURRENTLY`.",
            )
        )
    return findings


def _alter_column_type(
    statements: list[Statement], options: LintOptions, filename: str
) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in statements:
        text = stmt.normalized
        if not RE_ALTER_TABLE.match(text):
            continue
        match = RE_ALTER_COLUMN_TYPE.search(text)
        if not match:
            continue
        new_type = match.group(1)
        if RE_TYPE_IS_TEXT.match(new_type):
            continue  # varchar/char -> text is a documented no-op in Postgres
        findings.append(
            make_finding(
                RULE_ALTER_COLUMN_TYPE,
                stmt,
                filename,
                message=(
                    "ALTER COLUMN ... TYPE rewrites the table and every dependent index "
                    "unless it is a documented no-op (e.g. VARCHAR(n) -> VARCHAR(m) with "
                    "m > n, or VARCHAR/CHAR -> TEXT)."
                ),
                lock_info=(
                    "ACCESS EXCLUSIVE lock for the duration of the rewrite; blocks all "
                    "reads and writes on the table."
                ),
                dialect=Dialect.POSTGRES,
                version_range="all supported versions",
                safe_rewrite=(
                    "If only widening a VARCHAR length or moving to TEXT, this is a "
                    "metadata-only change and safe to ignore. Otherwise: add a new "
                    "column of the new type, backfill in batches, swap via a "
                    "transactional rename, or accept the rewrite in a maintenance "
                    "window."
                ),
            )
        )
    return findings


def _add_constraint_no_not_valid(
    statements: list[Statement], options: LintOptions, filename: str
) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in statements:
        text = stmt.normalized
        if not RE_ALTER_TABLE.match(text):
            continue
        if not RE_ADD_CONSTRAINT_FK_CHECK.search(text):
            continue
        if RE_NOT_VALID.search(text):
            continue
        findings.append(
            make_finding(
                RULE_ADD_CONSTRAINT_NOT_VALID,
                stmt,
                filename,
                message=(
                    "ADD CONSTRAINT (FOREIGN KEY/CHECK) without NOT VALID scans and "
                    "locks the full table to validate existing rows."
                ),
                lock_info=(
                    "SHARE ROW EXCLUSIVE lock (FK) or ACCESS EXCLUSIVE briefly (CHECK) "
                    "while every existing row is scanned; blocks writes for the scan's "
                    "duration."
                ),
                dialect=Dialect.POSTGRES,
                version_range="all supported versions",
                safe_rewrite=(
                    "Add the constraint with NOT VALID first (fast, only takes a brief "
                    "lock), then run `ALTER TABLE ... VALIDATE CONSTRAINT ...` "
                    "separately, which only needs a SHARE UPDATE EXCLUSIVE lock and "
                    "does not block writes."
                ),
            )
        )
    return findings


def _set_not_null(
    statements: list[Statement], options: LintOptions, filename: str
) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in statements:
        text = stmt.normalized
        if not RE_ALTER_TABLE.match(text):
            continue
        if not RE_SET_NOT_NULL.search(text):
            continue
        findings.append(
            make_finding(
                RULE_SET_NOT_NULL,
                stmt,
                filename,
                message="SET NOT NULL requires a full table scan to verify no NULLs exist.",
                lock_info=(
                    "ACCESS EXCLUSIVE lock for the duration of the scan; blocks reads "
                    "and writes."
                ),
                dialect=Dialect.POSTGRES,
                version_range="scan avoidable on 12+",
                safe_rewrite=(
                    "On Postgres 12+: add a `CHECK (col IS NOT NULL) NOT VALID` "
                    "constraint, validate it separately (cheap lock), then "
                    "`SET NOT NULL` (Postgres will skip the scan because the validated "
                    "CHECK already proves it)."
                ),
            )
        )
    return findings


def _rename_hazard(
    statements: list[Statement], options: LintOptions, filename: str
) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in statements:
        text = stmt.normalized
        if not RE_ALTER_TABLE.match(text):
            continue
        is_table_rename = RE_RENAME_TABLE.search(text) is not None
        is_column_rename = (
            "RENAME COLUMN" in text or RE_RENAME_COLUMN.search(text) is not None
        ) and not is_table_rename
        if not (is_table_rename or is_column_rename):
            continue
        what = "table" if is_table_rename else "column"
        findings.append(
            make_finding(
                RULE_RENAME_HAZARD,
                stmt,
                filename,
                message=(
                    f"Renaming a {what} takes only a brief lock, but application code "
                    "still running the previous release will fail as soon as the "
                    "rename commits."
                ),
                lock_info="ACCESS EXCLUSIVE lock, held briefly (catalog update only).",
                dialect=Dialect.POSTGRES,
                version_range="all supported versions",
                safe_rewrite=(
                    "Use an expand/contract deploy: introduce the new name alongside "
                    "the old one (view, generated column, or dual-write), ship "
                    "application code that supports both, then drop the old name in a "
                    "later migration."
                ),
            )
        )
    return findings


def _vacuum_cluster_reindex(
    statements: list[Statement], options: LintOptions, filename: str
) -> list[Finding]:
    findings: list[Finding] = []
    for stmt in statements:
        text = stmt.normalized
        if RE_VACUUM_FULL.match(text):
            findings.append(
                make_finding(
                    RULE_VACUUM_CLUSTER_REINDEX,
                    stmt,
                    filename,
                    message="VACUUM FULL rewrites the entire table and all its indexes.",
                    lock_info="ACCESS EXCLUSIVE lock for the whole rewrite; blocks all access.",
                    dialect=Dialect.POSTGRES,
                    version_range="all supported versions",
                    safe_rewrite=(
                        "Prefer `pg_repack` (rewrites without an extended exclusive "
                        "lock) or plain `VACUUM` plus routine autovacuum tuning to "
                        "avoid needing FULL at all."
                    ),
                )
            )
        elif RE_CLUSTER.match(text):
            findings.append(
                make_finding(
                    RULE_VACUUM_CLUSTER_REINDEX,
                    stmt,
                    filename,
                    message="CLUSTER rewrites the entire table in physical order.",
                    lock_info="ACCESS EXCLUSIVE lock for the whole rewrite; blocks all access.",
                    dialect=Dialect.POSTGRES,
                    version_range="all supported versions",
                    safe_rewrite=(
                        "Consider `pg_repack`, which can cluster/repack without "
                        "holding an extended exclusive lock."
                    ),
                )
            )
        elif RE_REINDEX.match(text) and not RE_CONCURRENTLY.search(text):
            findings.append(
                make_finding(
                    RULE_VACUUM_CLUSTER_REINDEX,
                    stmt,
                    filename,
                    message="REINDEX without CONCURRENTLY locks out writes while it rebuilds.",
                    lock_info=(
                        "ACCESS EXCLUSIVE lock on the table/index for the whole rebuild."
                    ),
                    dialect=Dialect.POSTGRES,
                    version_range="CONCURRENTLY available from 12+",
                    safe_rewrite="Use `REINDEX ... CONCURRENTLY` (Postgres 12+).",
                )
            )
    return findings


def _missing_lock_timeout(
    statements: list[Statement], options: LintOptions, filename: str
) -> list[Finding]:
    has_strong_lock = False
    first_strong: Statement | None = None
    for stmt in statements:
        for rule in _STRONG_LOCK_CHECKERS:
            if rule.check([stmt], options, filename):
                has_strong_lock = True
                if first_strong is None:
                    first_strong = stmt
                break
        if first_strong is not None:
            break

    if not has_strong_lock or first_strong is None:
        return []

    has_timeout = any(RE_SET_TIMEOUT.match(s.normalized) for s in statements)
    if has_timeout:
        return []

    return [
        make_finding(
            RULE_MISSING_LOCK_TIMEOUT,
            first_strong,
            filename,
            message=(
                "This migration takes a strong lock but sets no lock_timeout or "
                "statement_timeout. If the lock queues behind a long-running query, "
                "every later query on the table queues behind the migration too, "
                "turning a slow migration into an outage."
            ),
            lock_info=(
                "N/A (this finding is about the absence of a timeout guard, not a "
                "lock of its own)."
            ),
            dialect=Dialect.POSTGRES,
            version_range="all supported versions",
            safe_rewrite=(
                "Set `SET lock_timeout = '2s';` (and usually `statement_timeout`) at "
                "the top of the migration so a blocked DDL statement fails fast and "
                "can be retried, instead of queuing indefinitely."
            ),
        )
    ]


RULE_ADD_COLUMN_NOT_NULL_DEFAULT = Rule(
    id="PG001",
    name="add-column-not-null-default",
    default_severity=Severity.WARNING,
    dialects=(Dialect.POSTGRES,),
    check=_add_column_not_null_default,
    description="ADD COLUMN ... NOT NULL DEFAULT rewrites the table before Postgres 11.",
)
RULE_CREATE_INDEX_CONCURRENTLY = Rule(
    id="PG002",
    name="create-index-concurrently",
    default_severity=Severity.ERROR,
    dialects=(Dialect.POSTGRES,),
    check=_create_index_no_concurrently,
    description="CREATE INDEX without CONCURRENTLY blocks writes.",
)
RULE_DROP_INDEX_CONCURRENTLY = Rule(
    id="PG003",
    name="drop-index-concurrently",
    default_severity=Severity.WARNING,
    dialects=(Dialect.POSTGRES,),
    check=_drop_index_no_concurrently,
    description="DROP INDEX without CONCURRENTLY takes an exclusive lock.",
)
RULE_ALTER_COLUMN_TYPE = Rule(
    id="PG004",
    name="alter-column-type",
    default_severity=Severity.ERROR,
    dialects=(Dialect.POSTGRES,),
    check=_alter_column_type,
    description="ALTER COLUMN ... TYPE rewrites the table except for documented no-ops.",
)
RULE_ADD_CONSTRAINT_NOT_VALID = Rule(
    id="PG005",
    name="add-constraint-not-valid",
    default_severity=Severity.ERROR,
    dialects=(Dialect.POSTGRES,),
    check=_add_constraint_no_not_valid,
    description="ADD CONSTRAINT (FK/CHECK) without NOT VALID scans the full table.",
)
RULE_SET_NOT_NULL = Rule(
    id="PG006",
    name="set-not-null",
    default_severity=Severity.WARNING,
    dialects=(Dialect.POSTGRES,),
    check=_set_not_null,
    description="SET NOT NULL requires a full table scan.",
)
RULE_RENAME_HAZARD = Rule(
    id="PG007",
    name="rename-hazard",
    default_severity=Severity.WARNING,
    dialects=(Dialect.POSTGRES,),
    check=_rename_hazard,
    description="Renaming a table/column is a deploy-ordering hazard.",
)
RULE_VACUUM_CLUSTER_REINDEX = Rule(
    id="PG008",
    name="vacuum-cluster-reindex",
    default_severity=Severity.ERROR,
    dialects=(Dialect.POSTGRES,),
    check=_vacuum_cluster_reindex,
    description="VACUUM FULL / CLUSTER / REINDEX without CONCURRENTLY locks the table.",
)
RULE_MISSING_LOCK_TIMEOUT = Rule(
    id="PG009",
    name="missing-lock-timeout",
    default_severity=Severity.WARNING,
    dialects=(Dialect.POSTGRES,),
    check=_missing_lock_timeout,
    description="A strong-lock migration has no lock_timeout/statement_timeout guard.",
)

_STRONG_LOCK_CHECKERS = (
    RULE_ADD_COLUMN_NOT_NULL_DEFAULT,
    RULE_CREATE_INDEX_CONCURRENTLY,
    RULE_DROP_INDEX_CONCURRENTLY,
    RULE_ALTER_COLUMN_TYPE,
    RULE_ADD_CONSTRAINT_NOT_VALID,
    RULE_SET_NOT_NULL,
    RULE_VACUUM_CLUSTER_REINDEX,
)

RULES: tuple[Rule, ...] = (
    RULE_ADD_COLUMN_NOT_NULL_DEFAULT,
    RULE_CREATE_INDEX_CONCURRENTLY,
    RULE_DROP_INDEX_CONCURRENTLY,
    RULE_ALTER_COLUMN_TYPE,
    RULE_ADD_CONSTRAINT_NOT_VALID,
    RULE_SET_NOT_NULL,
    RULE_RENAME_HAZARD,
    RULE_VACUUM_CLUSTER_REINDEX,
    RULE_MISSING_LOCK_TIMEOUT,
)
