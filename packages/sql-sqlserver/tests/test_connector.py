"""Offline tests for SQLServerConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.sql.sqlserver.connector import (
    SQLServerConnector,
    _parse_dsn,
    _quote_ident,
)


def test_class_metadata() -> None:
    c = SQLServerConnector.__new__(SQLServerConnector)
    assert c.name == "sqlserver"


def test_parse_dsn() -> None:
    p = _parse_dsn("mssql://alice:s3cret@db.example.com:1434/myapp")
    assert p["server"] == "db.example.com"
    assert p["port"] == 1434
    assert p["user"] == "alice"
    assert p["password"] == "s3cret"
    assert p["database"] == "myapp"


def test_quote_ident_escapes_brackets() -> None:
    assert _quote_ident("a]b") == "[a]]b]"
    assert _quote_ident("plain") == "[plain]"


def test_query_guard_rejects_writes_before_connecting() -> None:
    c = SQLServerConnector("mssql://nobody:nope@127.0.0.1:1/no")
    with pytest.raises(WriteOperationError):
        c.query("DELETE FROM users")


def test_query_guard_rejects_drop() -> None:
    c = SQLServerConnector("mssql://nobody:nope@127.0.0.1:1/no")
    with pytest.raises(WriteOperationError):
        c.query("DROP TABLE users")
