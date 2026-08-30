from __future__ import annotations

from conftest import lint, rule_ids

# --- MY001: ALTER TABLE copy behavior ---------------------------------------


def test_my001_flags_alter_table_without_algorithm() -> None:
    findings = lint("ALTER TABLE users ADD COLUMN age INT;", dialect="mysql")
    assert "MY001" in rule_ids(findings)


def test_my001_clean_with_algorithm_inplace() -> None:
    findings = lint(
        "ALTER TABLE users ADD COLUMN age INT, ALGORITHM=INPLACE, LOCK=NONE;",
        dialect="mysql",
    )
    assert "MY001" not in rule_ids(findings)


def test_my001_clean_with_algorithm_instant() -> None:
    findings = lint(
        "ALTER TABLE users ADD COLUMN age INT, ALGORITHM=INSTANT;",
        dialect="mysql",
    )
    assert "MY001" not in rule_ids(findings)


def test_my001_does_not_run_under_postgres_dialect() -> None:
    findings = lint("ALTER TABLE users ADD COLUMN age INT;", dialect="postgres")
    assert "MY001" not in rule_ids(findings)


# --- MY002: implicit commit --------------------------------------------


def test_my002_flags_ddl_inside_explicit_transaction() -> None:
    sql = "START TRANSACTION;\nALTER TABLE users ADD COLUMN age INT;\nCOMMIT;\n"
    findings = lint(sql, dialect="mysql")
    assert "MY002" in rule_ids(findings)


def test_my002_flags_ddl_after_begin() -> None:
    sql = "BEGIN;\nDROP TABLE old_logs;\nCOMMIT;\n"
    findings = lint(sql, dialect="mysql")
    assert "MY002" in rule_ids(findings)


def test_my002_clean_without_explicit_transaction() -> None:
    sql = "ALTER TABLE users ADD COLUMN age INT, ALGORITHM=INSTANT;\n"
    findings = lint(sql, dialect="mysql")
    assert "MY002" not in rule_ids(findings)


def test_my002_clean_for_dml_only_transaction() -> None:
    sql = "START TRANSACTION;\nUPDATE users SET active = 1 WHERE id = 1;\nCOMMIT;\n"
    findings = lint(sql, dialect="mysql")
    assert "MY002" not in rule_ids(findings)
