"""Offline tests for MySQLConnector.

Live engine tests require a running MySQL instance. These tests cover the
parts that don't need one: DSN parsing, identifier quoting, and that the
parser guard fires *before* any connection attempt — bogus DSN, no panic.
"""

from __future__ import annotations

import pytest

from connectpak.core.guard import WriteOperationError
from connectpak.sql.mysql.connector import MySQLConnector, _parse_dsn, _quote_ident


def test_parse_dsn_full() -> None:
    p = _parse_dsn("mysql://alice:s3cret@db.example.com:3307/myapp")
    assert p == {
        "host": "db.example.com",
        "port": 3307,
        "user": "alice",
        "password": "s3cret",
        "database": "myapp",
    }


def test_parse_dsn_defaults() -> None:
    p = _parse_dsn("mysql://app@localhost/")
    assert p["host"] == "localhost"
    assert p["port"] == 3306
    assert p["user"] == "app"
    assert p["password"] is None
    assert p["database"] is None


def test_parse_dsn_url_encoded_password() -> None:
    p = _parse_dsn("mysql://u:p%40ss@h/d")
    assert p["password"] == "p@ss"


def test_parse_dsn_rejects_unknown_scheme() -> None:
    with pytest.raises(ValueError):
        _parse_dsn("postgres://u:p@h/d")


def test_quote_ident_escapes_backticks() -> None:
    assert _quote_ident("a`b") == "`a``b`"
    assert _quote_ident("plain") == "`plain`"


def test_query_guard_rejects_writes_before_connecting() -> None:
    c = MySQLConnector("mysql://nobody:nope@127.0.0.1:1/no")
    with pytest.raises(WriteOperationError):
        c.query("DELETE FROM users WHERE id = 1")


def test_query_guard_rejects_cte_with_delete() -> None:
    c = MySQLConnector("mysql://nobody:nope@127.0.0.1:1/no")
    with pytest.raises(WriteOperationError):
        c.query(
            "WITH gone AS (DELETE FROM users RETURNING id) SELECT * FROM gone"
        )
