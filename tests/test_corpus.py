"""Representative safe and dangerous migrations (tests/corpus/).

Every safe file must lint clean for a modern target (PostgreSQL 17) and exit
0; every dangerous file must produce exactly the listed findings and exit 1.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import lint

from sql_migrate_lint.cli import run

CORPUS = Path(__file__).parent / "corpus"

EXPECTED_DANGEROUS = {
    "01_unnamed_fk_and_check.sql": [("PG005", 2), ("PG005", 3)],
    "02_volatile_defaults.sql": [("PG001", 2), ("PG001", 3), ("PG001", 4)],
    "03_update_subquery_where.sql": [("GEN003", 1)],
    "04_drop_without_column_keyword.sql": [("GEN001", 1)],
    "05_timeout_after_ddl.sql": [("PG002", 1), ("PG009", 1)],
    "06_type_change.sql": [("PG004", 2), ("PG004", 3)],
}


def test_every_dangerous_file_has_an_expectation() -> None:
    names = sorted(p.name for p in (CORPUS / "dangerous").glob("*.sql"))
    assert names == sorted(EXPECTED_DANGEROUS)


@pytest.mark.parametrize("path", sorted((CORPUS / "safe").glob("*.sql")), ids=lambda p: p.name)
def test_safe_migration_is_clean(path: Path) -> None:
    findings = lint(path.read_text(encoding="utf-8"), target_version="17")
    assert [(f.rule_id, f.line) for f in findings] == []
    assert run([str(path), "--target-version", "17"]) == 0


@pytest.mark.parametrize("name", sorted(EXPECTED_DANGEROUS))
def test_dangerous_migration_is_flagged(name: str) -> None:
    path = CORPUS / "dangerous" / name
    findings = lint(path.read_text(encoding="utf-8"), target_version="17")
    assert sorted((f.rule_id, f.line) for f in findings) == sorted(EXPECTED_DANGEROUS[name])
    assert run([str(path), "--target-version", "17"]) == 1
