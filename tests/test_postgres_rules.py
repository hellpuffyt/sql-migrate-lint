from __future__ import annotations

from conftest import lint, rule_ids

# --- PG001: ADD COLUMN ... NOT NULL DEFAULT --------------------------------


def test_pg001_flags_add_column_not_null_default_no_target_version() -> None:
    findings = lint("ALTER TABLE users ADD COLUMN age INT NOT NULL DEFAULT 0;")
    assert "PG001" in rule_ids(findings)


def test_pg001_flags_add_column_not_null_default_target_version_9() -> None:
    findings = lint(
        "ALTER TABLE users ADD COLUMN age INT NOT NULL DEFAULT 0;",
        target_version="9.6",
    )
    assert "PG001" in rule_ids(findings)


def test_pg001_clean_on_target_version_11() -> None:
    findings = lint(
        "ALTER TABLE users ADD COLUMN age INT NOT NULL DEFAULT 0;",
        target_version="11+",
    )
    assert "PG001" not in rule_ids(findings)


def test_pg001_clean_on_target_version_12() -> None:
    findings = lint(
        "ALTER TABLE users ADD COLUMN age INT NOT NULL DEFAULT 0;",
        target_version="12",
    )
    assert "PG001" not in rule_ids(findings)


def test_pg001_clean_when_column_nullable() -> None:
    findings = lint("ALTER TABLE users ADD COLUMN age INT DEFAULT 0;")
    assert "PG001" not in rule_ids(findings)


def test_pg001_clean_when_no_default() -> None:
    findings = lint("ALTER TABLE users ADD COLUMN age INT NOT NULL;")
    assert "PG001" not in rule_ids(findings)


def test_pg001_message_mentions_lock() -> None:
    findings = lint("ALTER TABLE users ADD COLUMN age INT NOT NULL DEFAULT 0;")
    finding = next(f for f in findings if f.rule_id == "PG001")
    assert "ACCESS EXCLUSIVE" in finding.lock_info


# --- PG002: CREATE INDEX without CONCURRENTLY ------------------------------


def test_pg002_flags_create_index_without_concurrently() -> None:
    findings = lint("CREATE INDEX idx_a ON users (email);")
    assert "PG002" in rule_ids(findings)


def test_pg002_flags_unique_index_without_concurrently() -> None:
    findings = lint("CREATE UNIQUE INDEX idx_a ON users (email);")
    assert "PG002" in rule_ids(findings)


def test_pg002_clean_with_concurrently() -> None:
    findings = lint("CREATE INDEX CONCURRENTLY idx_a ON users (email);")
    assert "PG002" not in rule_ids(findings)


def test_pg002_clean_unique_with_concurrently() -> None:
    findings = lint("CREATE UNIQUE INDEX CONCURRENTLY idx_a ON users (email);")
    assert "PG002" not in rule_ids(findings)


# --- PG003: DROP INDEX without CONCURRENTLY --------------------------------


def test_pg003_flags_drop_index_without_concurrently() -> None:
    findings = lint("DROP INDEX idx_a;")
    assert "PG003" in rule_ids(findings)


def test_pg003_clean_with_concurrently() -> None:
    findings = lint("DROP INDEX CONCURRENTLY idx_a;")
    assert "PG003" not in rule_ids(findings)


# --- PG004: ALTER COLUMN TYPE ----------------------------------------------


def test_pg004_flags_alter_column_type() -> None:
    findings = lint("ALTER TABLE users ALTER COLUMN age TYPE bigint;")
    assert "PG004" in rule_ids(findings)


def test_pg004_clean_when_converting_to_text() -> None:
    findings = lint("ALTER TABLE users ALTER COLUMN bio TYPE text;")
    assert "PG004" not in rule_ids(findings)


def test_pg004_flags_varchar_length_change() -> None:
    findings = lint("ALTER TABLE users ALTER COLUMN name TYPE varchar(500);")
    assert "PG004" in rule_ids(findings)


# --- PG005: ADD CONSTRAINT FK/CHECK without NOT VALID ----------------------


def test_pg005_flags_add_foreign_key_without_not_valid() -> None:
    findings = lint(
        "ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) "
        "REFERENCES users(id);"
    )
    assert "PG005" in rule_ids(findings)


def test_pg005_clean_with_not_valid() -> None:
    findings = lint(
        "ALTER TABLE orders ADD CONSTRAINT fk_user FOREIGN KEY (user_id) "
        "REFERENCES users(id) NOT VALID;"
    )
    assert "PG005" not in rule_ids(findings)


def test_pg005_flags_check_constraint_without_not_valid() -> None:
    findings = lint("ALTER TABLE orders ADD CONSTRAINT chk_amt CHECK (amount > 0);")
    assert "PG005" in rule_ids(findings)


def test_pg005_clean_check_constraint_with_not_valid() -> None:
    findings = lint(
        "ALTER TABLE orders ADD CONSTRAINT chk_amt CHECK (amount > 0) NOT VALID;"
    )
    assert "PG005" not in rule_ids(findings)


def test_pg005_clean_for_unrelated_add_primary_key() -> None:
    findings = lint("ALTER TABLE orders ADD CONSTRAINT pk_orders PRIMARY KEY (id);")
    assert "PG005" not in rule_ids(findings)


# --- PG006: SET NOT NULL ----------------------------------------------------


def test_pg006_flags_set_not_null() -> None:
    findings = lint("ALTER TABLE users ALTER COLUMN email SET NOT NULL;")
    assert "PG006" in rule_ids(findings)


def test_pg006_clean_for_drop_not_null() -> None:
    findings = lint("ALTER TABLE users ALTER COLUMN email DROP NOT NULL;")
    assert "PG006" not in rule_ids(findings)


# --- PG007: rename hazard ---------------------------------------------------


def test_pg007_flags_table_rename() -> None:
    findings = lint("ALTER TABLE users RENAME TO customers;")
    assert "PG007" in rule_ids(findings)


def test_pg007_flags_column_rename() -> None:
    findings = lint("ALTER TABLE users RENAME COLUMN email TO email_address;")
    assert "PG007" in rule_ids(findings)


def test_pg007_clean_for_add_column() -> None:
    findings = lint("ALTER TABLE users ADD COLUMN nickname text;")
    assert "PG007" not in rule_ids(findings)


# --- PG008: VACUUM FULL / CLUSTER / REINDEX --------------------------------


def test_pg008_flags_vacuum_full() -> None:
    findings = lint("VACUUM FULL users;")
    assert "PG008" in rule_ids(findings)


def test_pg008_clean_plain_vacuum() -> None:
    findings = lint("VACUUM users;")
    assert "PG008" not in rule_ids(findings)


def test_pg008_flags_cluster() -> None:
    findings = lint("CLUSTER users USING idx_users_pkey;")
    assert "PG008" in rule_ids(findings)


def test_pg008_flags_reindex_without_concurrently() -> None:
    findings = lint("REINDEX TABLE users;")
    assert "PG008" in rule_ids(findings)


def test_pg008_clean_reindex_concurrently() -> None:
    findings = lint("REINDEX TABLE CONCURRENTLY users;")
    assert "PG008" not in rule_ids(findings)


# --- PG009: missing lock_timeout -------------------------------------------


def test_pg009_flags_missing_lock_timeout_with_strong_lock() -> None:
    findings = lint("CREATE INDEX idx_a ON users (email);")
    assert "PG009" in rule_ids(findings)


def test_pg009_clean_with_lock_timeout_set() -> None:
    findings = lint(
        "SET lock_timeout = '2s';\nCREATE INDEX idx_a ON users (email);"
    )
    assert "PG009" not in rule_ids(findings)


def test_pg009_clean_with_statement_timeout_set() -> None:
    findings = lint(
        "SET statement_timeout = '5s';\nCREATE INDEX idx_a ON users (email);"
    )
    assert "PG009" not in rule_ids(findings)


def test_pg009_clean_when_no_strong_lock_statements() -> None:
    findings = lint("SELECT 1;")
    assert "PG009" not in rule_ids(findings)


# --- ignore mechanics --------------------------------------------------


def test_ignore_suppresses_rule() -> None:
    findings = lint(
        "CREATE INDEX idx_a ON users (email);", ignore=frozenset({"PG002", "PG009"})
    )
    assert "PG002" not in rule_ids(findings)
    assert "PG009" not in rule_ids(findings)


def test_mysql_dialect_does_not_run_postgres_rules() -> None:
    findings = lint("CREATE INDEX idx_a ON users (email);", dialect="mysql")
    assert "PG002" not in rule_ids(findings)
