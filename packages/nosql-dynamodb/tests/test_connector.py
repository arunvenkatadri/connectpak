"""Offline tests for DynamoDBConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.nosql.dynamodb.connector import DynamoDBConnector


def test_class_metadata() -> None:
    c = DynamoDBConnector.__new__(DynamoDBConnector)
    assert c.name == "dynamodb"


def _conn() -> DynamoDBConnector:
    return DynamoDBConnector("us-east-1")


def test_marshal_basic_types() -> None:
    d = DynamoDBConnector._marshal(
        {"s": "hi", "n": 7, "f": 3.14, "b": True, "z": None}
    )
    assert d == {
        "s": {"S": "hi"},
        "n": {"N": "7"},
        "f": {"N": "3.14"},
        "b": {"BOOL": True},
        "z": {"NULL": True},
    }


def test_unmarshal_round_trip() -> None:
    d = DynamoDBConnector._unmarshal(
        {"s": {"S": "hi"}, "n": {"N": "7"}, "f": {"N": "3.14"},
         "b": {"BOOL": True}, "z": {"NULL": True}}
    )
    assert d == {"s": "hi", "n": 7, "f": 3.14, "b": True, "z": None}


def test_query_rejects_empty() -> None:
    with pytest.raises(WriteOperationError):
        _conn().query("")


def test_query_rejects_missing_op() -> None:
    with pytest.raises(WriteOperationError):
        _conn().query('{"table": "x"}')


def test_query_rejects_write_op() -> None:
    with pytest.raises(WriteOperationError):
        _conn().query('{"op": "put_item", "table": "x"}')


def test_query_rejects_partiql_write() -> None:
    with pytest.raises(WriteOperationError):
        _conn().query(
            '{"op": "execute_statement", "statement": "DELETE FROM users WHERE id = 1"}'
        )
