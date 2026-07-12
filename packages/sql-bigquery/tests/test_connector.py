"""Offline tests for BigQueryConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.sql.bigquery.connector import BigQueryConnector, _quote_ident


def test_class_metadata() -> None:
    c = BigQueryConnector.__new__(BigQueryConnector)
    assert c.name == "bigquery"


def test_quote_ident_wraps_in_backticks() -> None:
    assert _quote_ident("my_table") == "`my_table`"


def test_quote_ident_rejects_backtick_injection() -> None:
    # A hostile table name must not be able to break out of the quoting.
    with pytest.raises(ValueError):
        _quote_ident("t` ) UNION SELECT * FROM secrets --")


def test_query_guard_rejects_writes_before_connecting() -> None:
    c = BigQueryConnector.__new__(BigQueryConnector)
    c.allow_write = False
    c.dialect = 'bigquery'
    c.statement_timeout_ms = 1
    c.default_max_rows = 1
    with pytest.raises(WriteOperationError):
        c.query('DELETE FROM dataset.users WHERE TRUE')
