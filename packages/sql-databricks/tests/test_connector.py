"""Offline tests for DatabricksConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.sql.databricks.connector import DatabricksConnector


def test_class_metadata() -> None:
    c = DatabricksConnector.__new__(DatabricksConnector)
    assert c.name == "databricks"


def test_query_guard_rejects_writes_before_connecting() -> None:
    c = DatabricksConnector.__new__(DatabricksConnector)
    c.allow_write = False
    c.dialect = 'databricks'
    c.statement_timeout_ms = 1
    c.default_max_rows = 1
    with pytest.raises(WriteOperationError):
        c.query('DELETE FROM users')
