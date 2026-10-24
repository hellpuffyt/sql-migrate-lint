"""Check the linter's PostgreSQL facts against a real PostgreSQL server.

Opt-in: set ``SQL_MIGRATE_LINT_PG_BINDIR`` to a PostgreSQL ``bin`` directory
(containing ``initdb``, ``pg_ctl`` and ``psql``). The test creates a
throwaway cluster in a temporary directory, listening on a Unix socket only,
and removes it afterwards. Without the variable the tests are skipped (and
reported as skipped, never as passed); with the variable set, missing
binaries are a failure.

For every case it records whether PostgreSQL actually rewrote the table
(the table's relfilenode changes) or which lock mode it took, and compares
that with what the linter reports for ``--target-version`` = the server's
major version.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from conftest import lint

PG_BINDIR = os.environ.get("SQL_MIGRATE_LINT_PG_BINDIR")

pytestmark = pytest.mark.skipif(
    not PG_BINDIR,
    reason="set SQL_MIGRATE_LINT_PG_BINDIR to a PostgreSQL bin directory to run",
)

SETUP = (
    "DROP TABLE IF EXISTS t CASCADE; DROP TABLE IF EXISTS p CASCADE; DROP SEQUENCE IF EXISTS s;"
    "CREATE SEQUENCE s;"
    "CREATE TABLE p (id int PRIMARY KEY); INSERT INTO p SELECT g FROM generate_series(1, 500) g;"
    "CREATE TABLE t (id int PRIMARY KEY, v varchar(10), c char(5), n int, pid int);"
    "INSERT INTO t SELECT g, 'x', 'y', g, g FROM generate_series(1, 500) g;"
)

# (statement, does PostgreSQL rewrite t?, linter finding expected at the
#  server's version: (rule, severity) or None)
REWRITE_CASES = [
    ("ALTER TABLE t ADD COLUMN a int NOT NULL DEFAULT 0", False, None),
    ("ALTER TABLE t ADD COLUMN a timestamptz NOT NULL DEFAULT now()", False, None),
    ("ALTER TABLE t ADD COLUMN a text DEFAULT 'x'", False, None),
    (
        "ALTER TABLE t ADD COLUMN a timestamptz NOT NULL DEFAULT clock_timestamp()",
        True,
        ("PG001", "error"),
    ),
    ("ALTER TABLE t ADD COLUMN a uuid DEFAULT gen_random_uuid()", True, ("PG001", "error")),
    ("ALTER TABLE t ADD COLUMN a float8 NOT NULL DEFAULT random()", True, ("PG001", "error")),
    ("ALTER TABLE t ADD COLUMN a bigint NOT NULL DEFAULT nextval('s')", True, ("PG001", "error")),
    ("ALTER TABLE t ADD COLUMN a bigserial", True, ("PG001", "error")),
    ("ALTER TABLE t ADD COLUMN a int GENERATED ALWAYS AS IDENTITY", True, ("PG001", "error")),
    ("ALTER TABLE t ADD COLUMN a int GENERATED ALWAYS AS (n * 2) STORED", True, ("PG001", "error")),
    ("ALTER TABLE t ALTER COLUMN v TYPE text", False, ("PG004", "warning")),
    ("ALTER TABLE t ALTER COLUMN c TYPE text", True, ("PG004", "warning")),
    ("ALTER TABLE t ALTER COLUMN n TYPE text", True, ("PG004", "warning")),
    ("ALTER TABLE t ALTER COLUMN n TYPE bigint", True, ("PG004", "error")),
    # Documented limitation: widening VARCHAR is metadata-only but flagged,
    # because the old length is not visible in the statement.
    ("ALTER TABLE t ALTER COLUMN v TYPE varchar(20)", False, ("PG004", "error")),
]

# (statement, relation, lock mode PostgreSQL takes, rule that must fire)
LOCK_CASES = [
    ("CREATE INDEX ON t (n)", "t", "ShareLock", "PG002"),
    ("ALTER TABLE t ADD CHECK (n > 0)", "t", "AccessExclusiveLock", "PG005"),
    (
        "ALTER TABLE t ADD FOREIGN KEY (pid) REFERENCES p (id)",
        "t",
        "ShareRowExclusiveLock",
        "PG005",
    ),
    ("ALTER TABLE t ALTER COLUMN n SET NOT NULL", "t", "AccessExclusiveLock", "PG006"),
]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def psql() -> Iterator[Callable[[str], str]]:
    assert PG_BINDIR is not None
    bindir = Path(PG_BINDIR)
    for tool in ("initdb", "pg_ctl", "psql"):
        assert (bindir / tool).exists(), f"{tool} not found in SQL_MIGRATE_LINT_PG_BINDIR"
    # Short base path: Unix socket paths are limited to ~103 bytes on macOS.
    base = Path(tempfile.mkdtemp(prefix="sml"))
    data, port = base / "data", _free_port()
    try:
        subprocess.run(
            [str(bindir / "initdb"), "-D", str(data), "-A", "trust", "-U", "lint", "--no-locale"],
            check=True, capture_output=True,
        )
        subprocess.run(
            [str(bindir / "pg_ctl"), "-D", str(data), "-l", str(base / "log"), "-w", "-o",
             f"-k {base} -p {port} -c listen_addresses=''", "start"],
            check=True, capture_output=True,
        )

        def run(sql: str) -> str:
            out = subprocess.run(
                [str(bindir / "psql"), "-h", str(base), "-p", str(port), "-U", "lint",
                 "-d", "postgres", "-Atq", "-v", "ON_ERROR_STOP=1", "-c", sql],
                check=True, capture_output=True, text=True,
            )
            return out.stdout.strip()

        yield run
    finally:
        subprocess.run(
            [str(bindir / "pg_ctl"), "-D", str(data), "-m", "fast", "-w", "stop"],
            capture_output=True,
        )
        shutil.rmtree(base, ignore_errors=True)


@pytest.fixture(scope="module")
def major(psql: Callable[[str], str]) -> str:
    return psql("SHOW server_version_num")[:-4]


@pytest.mark.parametrize(
    ("sql", "rewrites", "expected"), REWRITE_CASES, ids=[c[0] for c in REWRITE_CASES]
)
def test_rewrite_behaviour_matches_linter(
    psql: Callable[[str], str],
    major: str,
    sql: str,
    rewrites: bool,
    expected: tuple[str, str] | None,
) -> None:
    psql(SETUP)
    before = psql("SELECT pg_relation_filenode('t')")
    psql(sql)
    after = psql("SELECT pg_relation_filenode('t')")
    assert (before != after) is rewrites, "PostgreSQL behaviour differs from the recorded fact"
    findings = [
        (f.rule_id, str(f.severity))
        for f in lint(sql + ";", target_version=major)
        if f.rule_id in ("PG001", "PG004")
    ]
    assert findings == ([expected] if expected else [])
    if rewrites:
        assert findings, "a rewriting statement must never lint clean"


@pytest.mark.parametrize(("sql", "rel", "mode", "rule"), LOCK_CASES, ids=[c[0] for c in LOCK_CASES])
def test_lock_modes_match_linter(
    psql: Callable[[str], str], major: str, sql: str, rel: str, mode: str, rule: str
) -> None:
    psql(SETUP)
    held = psql(
        f"BEGIN; {sql}; SELECT string_agg(l.mode, ',') FROM pg_locks l JOIN pg_class c "
        f"ON c.oid = l.relation WHERE c.relname = '{rel}' AND l.pid = pg_backend_pid(); ROLLBACK;"
    )
    assert mode in held.split(",")
    assert rule in {f.rule_id for f in lint(sql + ";", target_version=major)}
