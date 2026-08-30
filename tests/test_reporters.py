from __future__ import annotations

import json

from conftest import lint

from sql_migrate_lint.reporters import render_json, render_sarif, render_text


def test_render_text_no_issues() -> None:
    assert render_text([]) == "No issues found.\n"


def test_render_text_includes_rule_id_and_fix() -> None:
    findings = lint("CREATE INDEX idx_a ON users (email);")
    text = render_text(findings)
    assert "PG002" in text
    assert "fix:" in text
    assert "lock:" in text


def test_render_json_roundtrip() -> None:
    findings = lint("TRUNCATE users;")
    payload = json.loads(render_json(findings))
    assert payload["issue_count"] == len(findings)
    assert payload["findings"][0]["rule_id"] == "GEN002"


def test_render_json_empty() -> None:
    payload = json.loads(render_json([]))
    assert payload["issue_count"] == 0
    assert payload["findings"] == []


def test_render_sarif_structure() -> None:
    findings = lint("DELETE FROM sessions;")
    payload = json.loads(render_sarif(findings))
    assert payload["$schema"]
    run_obj = payload["runs"][0]
    assert run_obj["tool"]["driver"]["name"] == "sql-migrate-lint"
    rule_ids_in_sarif = {r["id"] for r in run_obj["tool"]["driver"]["rules"]}
    assert "GEN003" in rule_ids_in_sarif
    assert run_obj["results"][0]["ruleId"] == "GEN003"


def test_render_sarif_empty_results() -> None:
    payload = json.loads(render_sarif([]))
    assert payload["runs"][0]["results"] == []
