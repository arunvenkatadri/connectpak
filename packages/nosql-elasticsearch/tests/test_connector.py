"""Offline tests for ElasticsearchConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.nosql.elasticsearch.connector import ElasticsearchConnector


def test_class_metadata() -> None:
    c = ElasticsearchConnector.__new__(ElasticsearchConnector)
    assert c.name == "elasticsearch"


def _conn() -> ElasticsearchConnector:
    return ElasticsearchConnector("http://localhost:9200")


def test_query_rejects_empty() -> None:
    with pytest.raises(WriteOperationError):
        _conn().query("")


def test_query_rejects_invalid_json() -> None:
    with pytest.raises(WriteOperationError):
        _conn().query("not json")


def test_query_rejects_missing_op() -> None:
    with pytest.raises(WriteOperationError):
        _conn().query('{"index": "x"}')


def test_query_rejects_write_op() -> None:
    with pytest.raises(WriteOperationError):
        _conn().query('{"op": "index", "index": "x", "body": {}}')


def test_query_rejects_sql_delete() -> None:
    c = _conn()
    with pytest.raises(WriteOperationError):
        c.query('{"op": "sql", "query": "DELETE FROM idx WHERE id = 1"}')


def test_esql_guard_rejects_insert() -> None:
    c = _conn()
    with pytest.raises(WriteOperationError):
        c._guard_esql("INSERT INTO idx VALUES (1)")
