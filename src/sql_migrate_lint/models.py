"""Core data models shared across the parser, rules, and reporters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Dialect:
    """Supported SQL dialects."""

    POSTGRES = "postgres"
    MYSQL = "mysql"

    ALL = (POSTGRES, MYSQL)


class Severity(IntEnum):
    """Ordered finding severity, low to high."""

    INFO = 0
    WARNING = 1
    ERROR = 2
    CRITICAL = 3

    @classmethod
    def from_str(cls, value: str) -> Severity:
        try:
            return cls[value.strip().upper()]
        except KeyError as exc:
            valid = ", ".join(s.name.lower() for s in cls)
            raise ValueError(f"Unknown severity {value!r}; expected one of: {valid}") from exc

    def __str__(self) -> str:
        return self.name.lower()


@dataclass(frozen=True)
class Statement:
    """A single parsed SQL statement within a migration file."""

    text: str
    """The raw statement text, exactly as written (whitespace trimmed)."""

    line: int
    """1-based line number where the statement begins."""

    index: int
    """0-based position of the statement within the file."""

    normalized: str
    """Uppercased, whitespace-collapsed text used for keyword matching."""


@dataclass(frozen=True)
class Finding:
    """A single lint finding produced by a rule against a statement."""

    rule_id: str
    severity: Severity
    message: str
    file: str
    line: int
    statement: str
    lock_info: str
    dialect: str
    version_range: str
    safe_rewrite: str
    rule_name: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": str(self.severity),
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "statement": self.statement,
            "lock_info": self.lock_info,
            "dialect": self.dialect,
            "version_range": self.version_range,
            "safe_rewrite": self.safe_rewrite,
        }


@dataclass
class LintOptions:
    """Options controlling how rules evaluate a migration file."""

    dialect: str = Dialect.POSTGRES
    target_version: str | None = None
    ignore: frozenset[str] = field(default_factory=frozenset)
    rows_threshold: int | None = None
    small_tables: frozenset[str] = field(default_factory=frozenset)

    def target_major_version(self) -> int | None:
        """Parse a target version string like '11', '11+', '13.2' into a major int."""
        if not self.target_version:
            return None
        v = self.target_version.strip().rstrip("+")
        if not v:
            return None
        major = v.split(".")[0]
        try:
            return int(major)
        except ValueError:
            return None
