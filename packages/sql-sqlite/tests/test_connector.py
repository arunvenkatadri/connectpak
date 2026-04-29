"""End-to-end tests for SqliteConnector."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from connectpak.core.guard import WriteOperationError
from connectpak.sql.sqlite.connector import SqliteConnector


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            name TEXT
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            total REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE INDEX idx_orders_user_id ON orders(user_id);
        INSERT INTO users (id, email, name) VALUES
            (1, 'a@example.com', 'Alice'),
            (2, 'b@example.com', 'Bob'),
            (3, 'c@example.com', 'Carol');
        INSERT INTO orders (id, user_id, total) VALUES
            (1, 1, 10.0),
            (2, 1, 20.0),
            (3, 2, 30.0);
        """
    )
    conn.commit()
    conn.close()
    return str(path)


def test_list_schemas_and_tables(db_path: str) -> None:
    c = SqliteConnector(db_path)
    try:
        assert c.list_schemas() == ["main"]
        tables = c.list_tables()
        names = sorted(n for _, n in tables)
        assert names == ["orders", "users"]
    finally:
        c.close()


def test_describe_table(db_path: str) -> None:
    c = SqliteConnector(db_path)
    try:
        users = c.describe_table("users")
        assert users.primary_key == ["id"]
        assert {col.name for col in users.columns} == {"id", "email", "name"}

        orders = c.describe_table("orders")
        assert orders.primary_key == ["id"]
        assert len(orders.foreign_keys) == 1
        fk = orders.foreign_keys[0]
        assert fk.columns == ["user_id"]
        assert fk.referenced_table == "users"
        assert fk.referenced_columns == ["id"]
        idx_names = {i.name for i in orders.indexes}
        assert "idx_orders_user_id" in idx_names
    finally:
        c.close()


def test_sample_and_query(db_path: str) -> None:
    c = SqliteConnector(db_path)
    try:
        sample = c.sample_table("users", limit=2)
        assert sample.row_count == 2
        assert "email" in sample.columns

        result = c.query("SELECT id FROM users ORDER BY id")
        assert result.row_count == 3
        assert [r[0] for r in result.rows] == [1, 2, 3]
    finally:
        c.close()


def test_query_truncation(db_path: str) -> None:
    c = SqliteConnector(db_path)
    try:
        result = c.query("SELECT id FROM users ORDER BY id", max_rows=2)
        assert result.row_count == 2
        assert result.truncated is True
    finally:
        c.close()


def test_guard_rejects_writes(db_path: str) -> None:
    c = SqliteConnector(db_path)
    try:
        with pytest.raises(WriteOperationError):
            c.query("DELETE FROM users WHERE id = 1")
    finally:
        c.close()


def test_engine_level_read_only_blocks_direct_inserts(db_path: str) -> None:
    """Even if the parser guard were bypassed, the read-only URI mode blocks
    state mutation at the engine level."""
    c = SqliteConnector(db_path)
    try:
        conn = c._connection()
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO users (id, email) VALUES (99, 'x@example.com')")
    finally:
        c.close()


def test_explain_returns_non_empty(db_path: str) -> None:
    c = SqliteConnector(db_path)
    try:
        out = c.explain("SELECT * FROM users WHERE id = 1")
        assert isinstance(out, str)
        assert out.strip() != ""
    finally:
        c.close()


def test_allow_write_permits_inserts(db_path: str) -> None:
    c = SqliteConnector(db_path, allow_write=True)
    try:
        c._connection().execute(
            "INSERT INTO users (id, email, name) VALUES (10, 'd@example.com', 'Dan')"
        )
        c._connection().commit()
        cur = c._connection().execute("SELECT name FROM users WHERE id = 10")
        assert cur.fetchone()[0] == "Dan"
    finally:
        c.close()
