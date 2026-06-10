"""Offline tests for RedshiftConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.sql.redshift.connector import RedshiftConnector


def test_class_metadata() -> None:
    c = RedshiftConnector.__new__(RedshiftConnector)
    assert c.name == "redshift"


def test_query_guard_rejects_writes_before_connecting() -> None:
    c = RedshiftConnector.__new__(RedshiftConnector)
    c.allow_write = False
    c.dialect = 'redshift'
    c.statement_timeout_ms = 1
    c.default_max_rows = 1
    with pytest.raises(WriteOperationError):
        c.query('DELETE FROM users')
