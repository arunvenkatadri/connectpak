"""Tests for connectpak.core.guard.assert_read_only."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError, assert_read_only

ALLOWED = [
    "SELECT 1",
    "SELECT * FROM users WHERE id = 1",
    "SELECT id FROM a UNION SELECT id FROM b",
    "WITH active AS (SELECT id FROM users WHERE active) SELECT * FROM active",
    """
    SELECT u.id, COUNT(o.id) AS n
    FROM users u
    JOIN orders o ON o.user_id = u.id
    GROUP BY u.id
    """,
]

REJECTED = [
    "INSERT INTO users (id) VALUES (1)",
    "UPDATE users SET active = false",
    "DELETE FROM users WHERE id = 1",
    "DROP TABLE users",
    "CREATE TABLE foo (id INT)",
    "ALTER TABLE users ADD COLUMN x INT",
    "TRUNCATE TABLE users",
    "MERGE INTO users u USING staging s ON u.id = s.id "
    "WHEN MATCHED THEN UPDATE SET u.x = s.x",
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_allowed_read_statements(sql: str) -> None:
    assert_read_only(sql)


@pytest.mark.parametrize("sql", REJECTED)
def test_rejects_write_statements(sql: str) -> None:
    with pytest.raises(WriteOperationError):
        assert_read_only(sql)


def test_rejects_cte_with_delete() -> None:
    sql = (
        "WITH gone AS (DELETE FROM users WHERE active = false RETURNING id) "
        "SELECT * FROM gone"
    )
    with pytest.raises(WriteOperationError):
        assert_read_only(sql, dialect="postgres")


@pytest.mark.parametrize("sql", ["", "   ", "\n\t  "])
def test_rejects_empty_sql(sql: str) -> None:
    with pytest.raises(WriteOperationError):
        assert_read_only(sql)


# --- Hardening regressions: writes that hide inside an allowed Select shape ---


@pytest.mark.parametrize("dialect", ["tsql", "postgres"])
def test_rejects_select_into(dialect: str) -> None:
    """`SELECT ... INTO t` creates a table — a write inside a Select."""
    with pytest.raises(WriteOperationError):
        assert_read_only("SELECT * INTO new_table FROM users", dialect=dialect)


def test_rejects_select_into_nested_subquery() -> None:
    with pytest.raises(WriteOperationError):
        assert_read_only(
            "SELECT a INTO b FROM t WHERE id IN (SELECT id FROM other)",
            dialect="tsql",
        )


@pytest.mark.parametrize("sql", ["SELECT 1 FOR UPDATE", "SELECT 1 FOR SHARE"])
def test_rejects_locking_reads(sql: str) -> None:
    """Row-locking selects carry write intent and can block writers."""
    with pytest.raises(WriteOperationError):
        assert_read_only(sql, dialect="postgres")


@pytest.mark.parametrize(
    "sql",
    [
        "PRAGMA journal_mode=WAL",
        "PRAGMA foreign_keys=ON",
        "PRAGMA user_version=5",
        "PRAGMA synchronous=OFF",
    ],
)
def test_rejects_mutating_pragma(sql: str) -> None:
    with pytest.raises(WriteOperationError):
        assert_read_only(sql, dialect="sqlite")


@pytest.mark.parametrize(
    "sql",
    [
        "PRAGMA table_info(users)",
        "PRAGMA foreign_key_list(orders)",
        "PRAGMA index_list(users)",
        "PRAGMA user_version",
    ],
)
def test_allows_read_pragma(sql: str) -> None:
    assert_read_only(sql, dialect="sqlite")
