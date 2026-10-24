"""Regression tests for defects found in the production-readiness audit.

Facts about PostgreSQL behaviour asserted here were checked against a local
PostgreSQL 17 cluster; see tests/test_pg_ground_truth.py to re-check them.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import lint, rule_ids

from sql_migrate_lint.cli import run
from sql_migrate_lint.engine import lint_sql
from sql_migrate_lint.models import LintOptions


def ids_at(sql: str, version: str | None = "17") -> list[tuple[str, str]]:
    return [(f.rule_id, str(f.severity)) for f in lint(sql, target_version=version)]


@pytest.mark.parametrize(
    "sql",
    [
        "ALTER TABLE o ADD FOREIGN KEY (u) REFERENCES users (id);",
        "ALTER TABLE o ADD CHECK (amount > 0);",
    ],
)
def test_pg005_constraint_without_a_name(sql: str) -> None:
    # Before: only `ADD CONSTRAINT <name> ...` was recognised.
    assert "PG005" in rule_ids(lint(sql))
    assert "PG005" not in rule_ids(lint(sql.replace(";", " NOT VALID;")))


@pytest.mark.parametrize(
    "column",
    [
        "uid uuid NOT NULL DEFAULT gen_random_uuid()",
        "uid uuid DEFAULT gen_random_uuid()",
        "ts timestamptz NOT NULL DEFAULT clock_timestamp()",
        "r float8 NOT NULL DEFAULT random()",
        "s bigint NOT NULL DEFAULT nextval('s')",
        "seq bigserial",
        "i int GENERATED ALWAYS AS IDENTITY",
        "d int GENERATED ALWAYS AS (n * 2) STORED",
    ],
)
def test_pg001_volatile_additions_rewrite_even_on_pg11_plus(column: str) -> None:
    # Before: silent with --target-version >= 11 (and for nullable columns at
    # any version), although PostgreSQL 17 rewrites the table for all of these.
    assert ("PG001", "error") in ids_at(f"ALTER TABLE t ADD COLUMN {column};")


@pytest.mark.parametrize(
    "column",
    ["a int NOT NULL DEFAULT 0", "b timestamptz NOT NULL DEFAULT now()", "c text DEFAULT 'x'"],
)
def test_pg001_constant_and_stable_defaults_stay_clean_on_pg11_plus(column: str) -> None:
    assert "PG001" not in rule_ids(lint(f"ALTER TABLE t ADD COLUMN {column};", target_version="17"))


def test_pg004_type_text_with_using_is_an_error() -> None:
    assert ("PG004", "error") in ids_at("ALTER TABLE t ALTER COLUMN c TYPE text USING c::text;")


def test_gen003_where_inside_a_subquery_does_not_scope_the_update() -> None:
    # Before: any WHERE anywhere (even in a subquery) suppressed the finding.
    assert "GEN003" in rule_ids(lint("UPDATE u SET p = (SELECT id FROM plans WHERE n = 'f');"))
    assert "GEN003" not in rule_ids(
        lint("UPDATE u SET p = (SELECT id FROM plans WHERE n = 'f') WHERE u.id = 1;")
    )
    assert "GEN003" in rule_ids(lint("DELETE FROM u USING (SELECT 1 WHERE true) s;"))


@pytest.mark.parametrize(
    ("sql", "flagged"),
    [
        ("ALTER TABLE u DROP legacy;", True),
        ("ALTER TABLE u DROP IF EXISTS legacy;", True),
        ("ALTER TABLE u ADD COLUMN a int, DROP b;", True),
        ("ALTER TABLE u DROP CONSTRAINT u_check;", False),
        ("ALTER TABLE u ALTER COLUMN a DROP DEFAULT;", False),
        ("ALTER TABLE u ALTER COLUMN a DROP NOT NULL;", False),
        ("ALTER TABLE u DROP PRIMARY KEY;", False),
    ],
)
def test_gen001_drop_column_without_the_column_keyword(sql: str, flagged: bool) -> None:
    assert ("GEN001" in rule_ids(lint(sql))) is flagged


def test_pg009_timeout_must_come_before_the_strong_lock() -> None:
    # Before: a `SET lock_timeout` anywhere in the file (even after the DDL)
    # satisfied the rule.
    assert "PG009" in rule_ids(lint("CREATE INDEX i ON t (a);\nSET lock_timeout = '2s';"))
    assert "PG009" not in rule_ids(lint("SET lock_timeout = '2s';\nCREATE INDEX i ON t (a);"))


def test_lock_rules_do_not_fire_on_a_table_created_in_the_same_file() -> None:
    sql = 'CREATE TABLE things (id int);\nCREATE INDEX things_id ON things (id);'
    assert rule_ids(lint(sql)) == set()
    # A different table in the same file is still checked.
    sql2 = sql + "\nCREATE INDEX users_email ON users (email);"
    assert {"PG002", "PG009"} <= rule_ids(lint(sql2))


def test_quoted_identifiers_of_equal_length_are_not_confused() -> None:
    # Quoted names used to be masked to the same "xxxx" text.
    sql = 'CREATE TABLE "Abc" (id int);\nCREATE INDEX i ON "Xyz" (id);'
    assert "PG002" in rule_ids(lint(sql))
    same = 'CREATE TABLE "Abc" (id int);\nCREATE INDEX i ON "Abc" (id);'
    assert "PG002" not in rule_ids(lint(same))


def test_quoted_identifier_text_never_matches_keywords() -> None:
    sql = 'ALTER TABLE t ADD COLUMN "not null default" int;'
    assert rule_ids(lint(sql, target_version="10")) == set()


def test_small_table_downgrades_lock_findings_to_info() -> None:
    # Before: --small-table / --rows-threshold were accepted and ignored.
    opts = LintOptions(small_tables=frozenset({"countries"}), rows_threshold=500)
    findings = lint_sql("CREATE INDEX c ON countries (code);", "m.sql", opts)
    pg002 = [f for f in findings if f.rule_id == "PG002"]
    assert [str(f.severity) for f in pg002] == ["info"]
    assert "under 500 rows" in pg002[0].message
    assert "PG009" not in {f.rule_id for f in findings}
    # Irreversibility rules are never softened.
    drop = lint_sql("DROP TABLE countries;", "m.sql", opts)
    assert [str(f.severity) for f in drop] == ["warning"]


def test_cli_small_table_flag_changes_exit_code(tmp_path: Path) -> None:
    f = tmp_path / "m.sql"
    f.write_text("CREATE INDEX c ON countries (code);\n", encoding="utf-8")
    assert run([str(f)]) == 1
    assert run([str(f), "--small-table", "countries"]) == 0


def test_severity_threshold_also_filters_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # `--severity` is documented as the minimum severity "to report and to
    # fail the build on"; warnings used to be printed under --severity error.
    f = tmp_path / "m.sql"
    f.write_text("DROP TABLE legacy;\n", encoding="utf-8")
    assert run([str(f), "--severity", "error"]) == 0
    assert "GEN001" not in capsys.readouterr().out
    assert run([str(f)]) == 1
    assert "GEN001" in capsys.readouterr().out


def test_non_utf8_file_is_a_clean_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "m.sql"
    f.write_bytes(b"CREATE INDEX i ON t (a); -- \xff\xfe\n")
    assert run([str(f)]) == 2
    assert "not valid UTF-8" in capsys.readouterr().err
