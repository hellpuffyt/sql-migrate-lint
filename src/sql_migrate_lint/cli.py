"""Command-line entry point for sql-migrate-lint."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from sql_migrate_lint.engine import lint_sql
from sql_migrate_lint.models import Dialect, Finding, LintOptions, Severity
from sql_migrate_lint.parser import SqlParseError
from sql_migrate_lint.reporters import RENDERERS

SQL_EXTENSIONS = (".sql",)


def _discover_files(paths: Iterable[str]) -> list[Path]:
    """Expand a list of file/directory paths into a sorted list of .sql files.

    Directories are walked recursively, which supports the numbered-migration
    directory layout used by frameworks like Flyway, Alembic-adjacent SQL
    migrations, Sqitch, and plain `NNN_description.sql` folders.
    """
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(q for q in p.rglob("*.sql") if q.is_file()))
        elif p.is_file():
            files.append(p)
        else:
            raise FileNotFoundError(f"No such file or directory: {raw}")
    # De-duplicate while preserving order, in case a file is reachable twice.
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(f)
    return unique


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sql-migrate-lint",
        description=(
            "Lint SQL migrations for operations that lock tables, rewrite data, "
            "or are irreversible on a live database."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="SQL migration file(s) or directories to lint.",
    )
    parser.add_argument(
        "--dialect",
        choices=Dialect.ALL,
        default=Dialect.POSTGRES,
        help="SQL dialect to lint for (default: postgres).",
    )
    parser.add_argument(
        "--target-version",
        default=None,
        help=(
            "Target database major version (e.g. '11', '11+', '8.0'). Used to "
            "decide whether version-boundary rules apply."
        ),
    )
    parser.add_argument(
        "--severity",
        choices=[s.name.lower() for s in Severity],
        default="warning",
        help=(
            "Minimum severity to report and to fail the build on (default: warning)."
        ),
    )
    parser.add_argument(
        "--ignore",
        default="",
        help="Comma-separated rule IDs to skip, e.g. PG002,GEN003.",
    )
    parser.add_argument(
        "--rows-threshold",
        type=int,
        default=None,
        help=(
            "Row count the --small-table tables are declared to stay under; "
            "only quoted in the softened finding's message (the linter cannot "
            "check row counts)."
        ),
    )
    parser.add_argument(
        "--small-table",
        action="append",
        default=[],
        help=(
            "Table known to be small; lock/rewrite findings on it are downgraded "
            "to info (repeatable)."
        ),
    )
    parser.add_argument(
        "--format",
        choices=list(RENDERERS),
        default="text",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write the report to this file instead of stdout.",
    )
    return parser


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        files = _discover_files(args.paths)
    except FileNotFoundError as exc:
        print(f"sql-migrate-lint: {exc}", file=sys.stderr)
        return 2

    if not files:
        print("sql-migrate-lint: no .sql files found in the given paths.", file=sys.stderr)
        return 2

    ignore = frozenset(
        rule_id.strip() for rule_id in args.ignore.split(",") if rule_id.strip()
    )
    options = LintOptions(
        dialect=args.dialect,
        target_version=args.target_version,
        ignore=ignore,
        rows_threshold=args.rows_threshold,
        small_tables=frozenset(args.small_table),
    )
    threshold = Severity.from_str(args.severity)

    all_findings: list[Finding] = []
    had_parse_error = False
    for file in files:
        try:
            sql = _read_file(file)
        except OSError as exc:
            print(f"sql-migrate-lint: could not read {file}: {exc}", file=sys.stderr)
            had_parse_error = True
            continue
        except UnicodeDecodeError as exc:
            print(
                f"sql-migrate-lint: {file}: not valid UTF-8 (byte offset {exc.start})",
                file=sys.stderr,
            )
            had_parse_error = True
            continue
        try:
            findings = lint_sql(sql, str(file), options)
        except SqlParseError as exc:
            print(f"sql-migrate-lint: {file}: {exc}", file=sys.stderr)
            had_parse_error = True
            continue
        all_findings.extend(findings)

    # --severity is the minimum severity both to report and to fail on.
    all_findings = [f for f in all_findings if f.severity >= threshold]
    all_findings.sort(key=lambda f: (f.file, f.line, f.rule_id))

    renderer = RENDERERS[args.format]
    report = renderer(all_findings)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)

    if had_parse_error:
        return 2

    if any(f.severity >= threshold for f in all_findings):
        return 1
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
