"""Rule registry: combines generic, PostgreSQL, and MySQL rule sets."""

from __future__ import annotations

from sql_migrate_lint.rules import generic, mysql, postgres
from sql_migrate_lint.rules.base import Rule

ALL_RULES: tuple[Rule, ...] = generic.RULES + postgres.RULES + mysql.RULES

RULES_BY_ID: dict[str, Rule] = {rule.id: rule for rule in ALL_RULES}

__all__ = ["ALL_RULES", "RULES_BY_ID", "Rule"]
