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
