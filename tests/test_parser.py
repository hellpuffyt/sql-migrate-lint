from __future__ import annotations

from sql_migrate_lint.parser import split_statements


def test_splits_multiple_statements() -> None:
    sql = "CREATE TABLE a (id int); CREATE TABLE b (id int);"
    stmts = split_statements(sql)
    assert len(stmts) == 2
    assert stmts[0].text.startswith("CREATE TABLE a")
    assert stmts[1].text.startswith("CREATE TABLE b")


def test_statement_indices_increment() -> None:
    sql = "SELECT 1; SELECT 2; SELECT 3;"
    stmts = split_statements(sql)
    assert [s.index for s in stmts] == [0, 1, 2]


def test_line_numbers_multiline_statement() -> None:
    sql = "CREATE TABLE a (\n  id int,\n  name text\n);\n\nDROP TABLE b;\n"
    stmts = split_statements(sql)
    assert stmts[0].line == 1
    assert stmts[1].line == 6


def test_leading_comment_does_not_shift_line_number() -> None:
    sql = "-- a helpful comment\n-- second line\nCREATE INDEX x ON y (z);\n"
    stmts = split_statements(sql)
    assert len(stmts) == 1
    assert stmts[0].line == 3
    assert stmts[0].text.startswith("CREATE INDEX")


def test_dash_dash_inside_string_literal_not_treated_as_comment() -> None:
    sql = "INSERT INTO notes (body) VALUES ('use -- as a bullet, not a comment');\n"
    stmts = split_statements(sql)
    assert len(stmts) == 1
    assert "bullet" in stmts[0].text


def test_semicolon_inside_string_literal_does_not_split_statement() -> None:
    sql = "INSERT INTO notes (body) VALUES ('first; second');\n"
    stmts = split_statements(sql)
    assert len(stmts) == 1


def test_block_comment_stripped_from_normalized() -> None:
    sql = "/* multi\nline\ncomment */\nSELECT 1;\n"
    stmts = split_statements(sql)
    assert len(stmts) == 1
    assert stmts[0].normalized == "SELECT 1;"


def test_keyword_inside_string_literal_does_not_match_normalized_as_keyword() -> None:
    sql = "INSERT INTO logs (message) VALUES ('please drop table later, manually');\n"
    stmts = split_statements(sql)
    normalized = stmts[0].normalized
    assert "DROP" not in normalized
    assert "TABLE" not in normalized
    assert "'" + "X" * len("please drop table later, manually") + "'" in normalized


def test_empty_file_yields_no_statements() -> None:
    assert split_statements("") == []


def test_whitespace_only_file_yields_no_statements() -> None:
    assert split_statements("   \n\n\t  \n") == []


def test_comment_only_file_yields_no_statements() -> None:
    assert split_statements("-- just a comment\n-- another one\n") == []


def test_malformed_sql_does_not_raise() -> None:
    stmts = split_statements("CREATE TABLE (((( invalid ???? ;;; garbage")
    assert isinstance(stmts, list)


def test_normalized_is_uppercased() -> None:
    sql = "select 1;"
    stmts = split_statements(sql)
    assert stmts[0].normalized == "SELECT 1;"


def test_multiple_statements_correct_line_numbers() -> None:
    sql = "SELECT 1;\n\nSELECT 2;\n\n\nSELECT 3;\n"
    stmts = split_statements(sql)
    assert [s.line for s in stmts] == [1, 3, 6]
