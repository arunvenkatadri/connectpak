"""Offline tests for OracleConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest

from connectpak.core.guard import WriteOperationError
from connectpak.sql.oracle.connector import OracleConnector


def test_class_metadata() -> None:
    c = OracleConnector.__new__(OracleConnector)
    assert c.name == "oracle"


def test_query_guard_rejects_writes_before_connecting() -> None:
    c = OracleConnector.__new__(OracleConnector)
    c.allow_write = False
    c.dialect = 'oracle'
    c.statement_timeout_ms = 1
    c.default_max_rows = 1
    with pytest.raises(WriteOperationError):
        c.query('DELETE FROM users')
