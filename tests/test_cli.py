from __future__ import annotations

import json
from pathlib import Path

import pytest

from sql_migrate_lint.cli import run


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_exit_zero_on_clean_migration(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = _write(tmp_path, "clean.sql", "CREATE INDEX CONCURRENTLY idx_a ON users (email);\n")
    code = run([str(f)])
    out = capsys.readouterr().out
    assert code == 0
    assert "No issues found" in out


def test_exit_nonzero_on_dangerous_migration(tmp_path: Path) -> None:
    f = _write(tmp_path, "danger.sql", "CREATE INDEX idx_a ON users (email);\n")
    code = run([str(f)])
    assert code == 1


def test_exit_two_on_missing_file() -> None:
    code = run(["does-not-exist.sql"])
    assert code == 2


def test_exit_two_on_no_sql_files_in_directory(tmp_path: Path) -> None:
    (tmp_path / "readme.txt").write_text("hello", encoding="utf-8")
    code = run([str(tmp_path)])
    assert code == 2


def test_lints_directory_recursively(tmp_path: Path) -> None:
    sub = tmp_path / "migrations"
    sub.mkdir()
    _write(sub, "0001_create.sql", "CREATE TABLE a (id int);\n")
    _write(sub, "0002_index.sql", "CREATE INDEX idx_a ON a (id);\n")
    code = run([str(sub)])
    assert code == 1  # the second file has a real finding


def test_ignore_flag_suppresses_rule(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = _write(tmp_path, "danger.sql", "CREATE INDEX idx_a ON users (email);\n")
    code = run([str(f), "--ignore", "PG002,PG009"])
    out = capsys.readouterr().out
    assert code == 0
    assert "No issues found" in out


def test_severity_threshold_error_only(tmp_path: Path) -> None:
    # PG007 (rename) defaults to warning; raising the threshold to error should
    # make an otherwise-failing file pass.
    f = _write(tmp_path, "rename.sql", "ALTER TABLE users RENAME TO customers;\n")
    code = run([str(f), "--severity", "error"])
    assert code == 0


def test_json_output_is_valid_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = _write(tmp_path, "danger.sql", "CREATE INDEX idx_a ON users (email);\n")
    run([str(f), "--format", "json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["issue_count"] >= 1
    assert payload["findings"][0]["rule_id"]


def test_sarif_output_has_expected_shape(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = _write(tmp_path, "danger.sql", "CREATE INDEX idx_a ON users (email);\n")
    run([str(f), "--format", "sarif"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["version"] == "2.1.0"
    assert payload["runs"][0]["results"]


def test_output_file_written(tmp_path: Path) -> None:
    f = _write(tmp_path, "danger.sql", "CREATE INDEX idx_a ON users (email);\n")
    out_path = tmp_path / "report.json"
    run([str(f), "--format", "json", "--output", str(out_path)])
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["issue_count"] >= 1


def test_mysql_dialect_flag(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    f = _write(tmp_path, "m.sql", "ALTER TABLE users ADD COLUMN age INT;\n")
    code = run([str(f), "--dialect", "mysql"])
    out = capsys.readouterr().out
    assert code == 1
    assert "MY001" in out


def test_target_version_flag_changes_pg001(tmp_path: Path) -> None:
    f = _write(
        tmp_path, "add.sql", "ALTER TABLE users ADD COLUMN age INT NOT NULL DEFAULT 0;\n"
    )
    code_old = run([str(f), "--target-version", "9.6"])
    code_new = run([str(f), "--target-version", "11+"])
    assert code_old == 1
    assert code_new == 0
