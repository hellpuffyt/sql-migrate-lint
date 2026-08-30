"""Statement splitting and normalization on top of sqlparse.

sqlparse tokenizes the whole file, including comments and string literals, so we
lean on its token stream rather than naive string splitting. This means a ``--``
inside a quoted string literal is never mistaken for a line comment, and a `;`
inside a string or comment never splits a statement early.
"""

from __future__ import annotations

import sqlparse
from sqlparse import tokens as T
from sqlparse.sql import Comment as SqlparseComment
from sqlparse.sql import Statement as SqlparseStatement

from sql_migrate_lint.models import Statement


def _is_comment_token(tok: object) -> bool:
    ttype = getattr(tok, "ttype", None)
    if ttype in T.Comment or str(ttype).startswith("Token.Comment"):
        return True
    return isinstance(tok, SqlparseComment)


class SqlParseError(Exception):
    """Raised when a migration file cannot be tokenized at all."""


def _is_blank(stmt: SqlparseStatement) -> bool:
    """True if a parsed chunk carries no real SQL (only whitespace/comments/punctuation)."""
    for tok in stmt.flatten():  # type: ignore[no-untyped-call]
        if tok.ttype in (T.Whitespace, T.Newline):
            continue
        if _is_comment_token(tok):
            continue
        if tok.ttype is T.Punctuation and tok.value == ";":
            continue
        return False
    return True


def _normalize(stmt: SqlparseStatement) -> str:
    """Build an uppercased, comment-stripped, string-masked form for keyword matching.

    Comments are dropped entirely and string/quoted-literal contents are replaced
    with ``x`` characters (keeping delimiters) so that keywords appearing inside a
    string literal (e.g. a column named ``'drop_table'``) never match rule regexes.
    """
    pieces: list[str] = []
    for tok in stmt.flatten():  # type: ignore[no-untyped-call]
        ttype = tok.ttype
        if _is_comment_token(tok):
            pieces.append(" ")
            continue
        if ttype in T.Literal.String or str(ttype).startswith("Token.Literal.String"):
            value = tok.value
            masked = (
                value[0] + "x" * (len(value) - 2) + value[-1] if len(value) >= 2 else value
            )
            pieces.append(masked)
            continue
        pieces.append(tok.value)
    text = "".join(pieces)
    collapsed = " ".join(text.split())
    return collapsed.upper()


def split_statements(sql: str) -> list[Statement]:
    """Split a migration file's SQL text into individual, line-numbered statements.

    Raises SqlParseError if sqlparse cannot tokenize the input at all (this is rare;
    sqlparse is tolerant, but a completely empty/whitespace-only file still yields
    zero statements, which is a valid, empty result rather than an error).
    """
    try:
        raw_statements = sqlparse.parse(sql)
    except Exception as exc:  # pragma: no cover - sqlparse is very tolerant
        raise SqlParseError(f"Failed to parse SQL: {exc}") from exc

    statements: list[Statement] = []
    offset = 0
    stmt_index = 0
    for raw in raw_statements:
        raw_text = str(raw)
        start_offset = offset
        offset += len(raw_text)

        if _is_blank(raw):
            continue

        # Find where the real SQL starts within this chunk, skipping any leading
        # whitespace and leading comments, so the reported line points at the
        # statement itself rather than at a comment sitting above it.
        code_offset_within_stmt = 0
        code_start_index = 0
        for i, tok in enumerate(raw.tokens):
            is_ws = tok.ttype in (T.Whitespace, T.Newline)
            is_comment = _is_comment_token(tok)
            if is_ws or is_comment:
                code_offset_within_stmt += len(str(tok))
                continue
            code_start_index = i
            break
        else:
            code_start_index = len(raw.tokens)

        stmt_start_offset = start_offset + code_offset_within_stmt
        line = 1 + sql.count("\n", 0, stmt_start_offset)

        code_text = "".join(str(t) for t in raw.tokens[code_start_index:]).strip()
        if not code_text:
            code_text = raw_text.strip()

        normalized = _normalize(raw)
        statements.append(
            Statement(
                text=code_text,
                line=line,
                index=stmt_index,
                normalized=normalized,
            )
        )
        stmt_index += 1

    return statements
