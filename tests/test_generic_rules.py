from __future__ import annotations

from conftest import lint, rule_ids

# --- GEN001: irreversible drops ---------------------------------------------


def test_gen001_flags_drop_table() -> None:
    findings = lint("DROP TABLE users;")
    assert "GEN001" in rule_ids(findings)


def test_gen001_flags_drop_table_if_exists() -> None:
    findings = lint("DROP TABLE IF EXISTS users;")
    assert "GEN001" in rule_ids(findings)


def test_gen001_flags_drop_column() -> None:
    findings = lint("ALTER TABLE users DROP COLUMN age;")
    assert "GEN001" in rule_ids(findings)


def test_gen001_clean_for_add_column() -> None:
    findings = lint("ALTER TABLE users ADD COLUMN age int;")
    assert "GEN001" not in rule_ids(findings)


def test_gen001_clean_for_create_table() -> None:
    findings = lint("CREATE TABLE users (id int);")
    assert "GEN001" not in rule_ids(findings)


def test_gen001_applies_to_mysql_too() -> None:
    findings = lint("DROP TABLE users;", dialect="mysql")
    assert "GEN001" in rule_ids(findings)


# --- GEN002: TRUNCATE --------------------------------------------------


def test_gen002_flags_truncate() -> None:
    findings = lint("TRUNCATE users;")
    assert "GEN002" in rule_ids(findings)


def test_gen002_flags_truncate_table() -> None:
    findings = lint("TRUNCATE TABLE users;")
    assert "GEN002" in rule_ids(findings)


def test_gen002_clean_for_delete_with_where() -> None:
    findings = lint("DELETE FROM users WHERE id = 1;")
    assert "GEN002" not in rule_ids(findings)


# --- GEN003: UPDATE/DELETE without WHERE -----------------------------------


def test_gen003_flags_update_without_where() -> None:
    findings = lint("UPDATE users SET active = false;")
    assert "GEN003" in rule_ids(findings)


def test_gen003_clean_update_with_where() -> None:
    findings = lint("UPDATE users SET active = false WHERE id = 1;")
    assert "GEN003" not in rule_ids(findings)


def test_gen003_flags_delete_without_where() -> None:
    findings = lint("DELETE FROM sessions;")
    assert "GEN003" in rule_ids(findings)


def test_gen003_clean_delete_with_where() -> None:
    findings = lint("DELETE FROM sessions WHERE expires_at < now();")
    assert "GEN003" not in rule_ids(findings)


def test_gen003_clean_for_select() -> None:
    findings = lint("SELECT * FROM users;")
    assert "GEN003" not in rule_ids(findings)


def test_gen003_applies_regardless_of_dialect() -> None:
    findings = lint("UPDATE users SET active = false;", dialect="mysql")
    assert "GEN003" in rule_ids(findings)


# --- multi-statement files ---------------------------------------------


def test_multi_statement_file_flags_each_independently() -> None:
    sql = (
        "CREATE INDEX idx_a ON users (email);\n"
        "TRUNCATE sessions;\n"
        "DELETE FROM logs;\n"
    )
    findings = lint(sql)
    ids = rule_ids(findings)
    assert "PG002" in ids
    assert "GEN002" in ids
    assert "GEN003" in ids


def test_clean_migration_produces_no_findings() -> None:
    sql = (
        "SET lock_timeout = '2s';\n"
        "CREATE INDEX CONCURRENTLY idx_a ON users (email);\n"
        "ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) "
        "REFERENCES users(id) NOT VALID;\n"
        "ALTER TABLE orders VALIDATE CONSTRAINT fk_user;\n"
    )
    findings = lint(sql)
    assert findings == []
