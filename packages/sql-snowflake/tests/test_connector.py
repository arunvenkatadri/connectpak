"""Offline tests for SnowflakeConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.sql.snowflake.connector import SnowflakeConnector


def test_class_metadata() -> None:
    c = SnowflakeConnector.__new__(SnowflakeConnector)
    assert c.name == "snowflake"


def test_query_guard_rejects_writes_before_connecting() -> None:
    c = SnowflakeConnector.__new__(SnowflakeConnector)
    c.allow_write = False
    c.dialect = 'snowflake'
    c.statement_timeout_ms = 1
    c.default_max_rows = 1
    with pytest.raises(WriteOperationError):
        c.query('DELETE FROM users')
