"""Offline tests for ClickHouseConnector.

Live engine tests require a running ClickHouse instance. These tests cover
DSN parsing, identifier quoting, type-nullability detection, and that the
parser guard fires before any HTTP request.
"""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.sql.clickhouse.connector import (
    ClickHouseConnector,
    _is_nullable,
    _parse_dsn,
    _quote_ident,
)


def test_parse_dsn_full() -> None:
    p = _parse_dsn("clickhouse://alice:s3cret@ch.example.com:9000/analytics")
    assert p["host"] == "ch.example.com"
    assert p["port"] == 9000
    assert p["username"] == "alice"
    assert p["password"] == "s3cret"
    assert p["database"] == "analytics"
    assert p["secure"] is False


def test_parse_dsn_defaults_to_default_user_and_db() -> None:
    p = _parse_dsn("clickhouse://localhost")
    assert p["username"] == "default"
    assert p["password"] == ""
    assert p["database"] == "default"
    assert p["port"] == 8123


def test_parse_dsn_https_secure_port() -> None:
    p = _parse_dsn("https://u:p@host/db")
    assert p["secure"] is True
    assert p["port"] == 8443


def test_quote_ident_escapes_backticks() -> None:
    assert _quote_ident("a`b") == "`a``b`"


def test_is_nullable_detects_wrapper() -> None:
    assert _is_nullable("Nullable(String)") is True
    assert _is_nullable("Nullable(Int64)") is True
    assert _is_nullable("String") is False
    assert _is_nullable("Array(String)") is False


def test_query_guard_rejects_writes_before_connecting() -> None:
    c = ClickHouseConnector("clickhouse://nobody:nope@127.0.0.1:1/no")
    with pytest.raises(WriteOperationError):
        c.query("INSERT INTO events VALUES (1, 2, 3)")


def test_query_guard_rejects_drop() -> None:
    c = ClickHouseConnector("clickhouse://nobody:nope@127.0.0.1:1/no")
    with pytest.raises(WriteOperationError):
        c.query("DROP TABLE events")
