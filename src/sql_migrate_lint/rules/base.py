"""Rule definitions and shared regex helpers."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from sql_migrate_lint.models import Finding, LintOptions, Severity, Statement

RuleCheck = Callable[[list[Statement], LintOptions, str], list[Finding]]


@dataclass(frozen=True)
class Rule:
    """Metadata plus the check function for a single lint rule."""

    id: str
    name: str
    default_severity: Severity
    dialects: tuple[str, ...]
    check: RuleCheck
    description: str = ""


def make_finding(
    rule: Rule,
    statement: Statement,
    filename: str,
    *,
    message: str,
    lock_info: str,
    dialect: str,
    version_range: str,
    safe_rewrite: str,
    severity: Severity | None = None,
) -> Finding:
    return Finding(
        rule_id=rule.id,
        rule_name=rule.name,
        severity=severity if severity is not None else rule.default_severity,
        message=message,
        file=filename,
        line=statement.line,
        statement=statement.text,
        lock_info=lock_info,
        dialect=dialect,
        version_range=version_range,
        safe_rewrite=safe_rewrite,
    )


# --- shared regex fragments -------------------------------------------------

IDENT = r"(?:\"[^\"]+\"|`[^`]+`|[A-Za-z_][A-Za-z0-9_.]*)"

RE_ALTER_TABLE = re.compile(rf"^ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?({IDENT})", re.I)
RE_CREATE_INDEX = re.compile(r"^CREATE\s+(UNIQUE\s+)?INDEX\b", re.I)
RE_DROP_INDEX = re.compile(r"^DROP\s+INDEX\b", re.I)
RE_DROP_TABLE = re.compile(rf"^DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?({IDENT})", re.I)
RE_TRUNCATE = re.compile(r"^TRUNCATE\b", re.I)
RE_UPDATE = re.compile(r"^UPDATE\b", re.I)
RE_DELETE = re.compile(r"^DELETE\s+FROM\b", re.I)
RE_VACUUM_FULL = re.compile(r"^VACUUM\s+(?:\([^)]*FULL[^)]*\)|FULL\b)", re.I)
RE_CLUSTER = re.compile(r"^CLUSTER\b", re.I)
RE_REINDEX = re.compile(r"^REINDEX\b", re.I)
RE_SET_TIMEOUT = re.compile(r"^SET\s+(LOCAL\s+)?(LOCK_TIMEOUT|STATEMENT_TIMEOUT)\b", re.I)
RE_WHERE = re.compile(r"\bWHERE\b", re.I)
RE_CONCURRENTLY = re.compile(r"\bCONCURRENTLY\b", re.I)


def contains_whole_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None
