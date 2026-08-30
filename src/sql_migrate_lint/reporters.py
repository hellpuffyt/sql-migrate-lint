"""Render findings as human text, JSON, or SARIF."""

from __future__ import annotations

import json
from typing import Any

from sql_migrate_lint.models import Finding, Severity
from sql_migrate_lint.version import __version__

_SEVERITY_LABEL = {
    Severity.INFO: "INFO",
    Severity.WARNING: "WARNING",
    Severity.ERROR: "ERROR",
    Severity.CRITICAL: "CRITICAL",
}

_SARIF_LEVEL = {
    Severity.INFO: "note",
    Severity.WARNING: "warning",
    Severity.ERROR: "error",
    Severity.CRITICAL: "error",
}


def render_text(findings: list[Finding]) -> str:
    if not findings:
        return "No issues found.\n"

    lines: list[str] = []
    for f in findings:
        lines.append(f"{f.file}:{f.line}: [{_SEVERITY_LABEL[f.severity]}] {f.rule_id} {f.message}")
        lines.append(f"  statement: {f.statement}")
        lines.append(f"  lock:      {f.lock_info}")
        lines.append(f"  dialect:   {f.dialect}  (version range: {f.version_range})")
        lines.append(f"  fix:       {f.safe_rewrite}")
        lines.append("")

    counts: dict[Severity, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    summary = ", ".join(
        f"{counts[s]} {_SEVERITY_LABEL[s].lower()}"
        for s in sorted(counts, reverse=True)
        if counts.get(s)
    )
    lines.append(f"{len(findings)} issue(s) found ({summary}).")
    return "\n".join(lines) + "\n"


def render_json(findings: list[Finding]) -> str:
    payload = {
        "version": __version__,
        "issue_count": len(findings),
        "findings": [f.to_dict() for f in findings],
    }
    return json.dumps(payload, indent=2) + "\n"


def render_sarif(findings: list[Finding]) -> str:
    rule_ids = sorted({f.rule_id for f in findings})
    rule_names = {f.rule_id: f.rule_name for f in findings}

    rules_def: list[dict[str, Any]] = [
        {
            "id": rid,
            "name": rule_names.get(rid, rid),
            "shortDescription": {"text": rule_names.get(rid, rid)},
        }
        for rid in rule_ids
    ]

    results: list[dict[str, Any]] = []
    for f in findings:
        results.append(
            {
                "ruleId": f.rule_id,
                "level": _SARIF_LEVEL[f.severity],
                "message": {"text": f"{f.message} Lock: {f.lock_info} Fix: {f.safe_rewrite}"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": f.file},
                            "region": {"startLine": max(f.line, 1)},
                        }
                    }
                ],
            }
        )

    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "sql-migrate-lint",
                        "version": __version__,
                        "informationUri": "https://github.com/hellpuffyt/sql-migrate-lint",
                        "rules": rules_def,
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, indent=2) + "\n"


RENDERERS = {
    "text": render_text,
    "json": render_json,
    "sarif": render_sarif,
}
