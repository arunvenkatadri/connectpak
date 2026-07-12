"""Offline tests for MongoDBConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.nosql.mongodb.connector import MongoDBConnector, _infer_type


def test_class_metadata() -> None:
    c = MongoDBConnector.__new__(MongoDBConnector)
    assert c.name == "mongodb"


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, "null"),
        (True, "bool"),
        (42, "int"),
        (3.14, "double"),
        ("x", "string"),
        ([1, 2], "array"),
        ({"a": 1}, "object"),
    ],
)
def test_infer_type(value, expected: str) -> None:
    assert _infer_type(value) == expected


def _conn() -> MongoDBConnector:
    return MongoDBConnector("mongodb://nobody:nope@127.0.0.1:1/no")


def test_query_rejects_empty() -> None:
    with pytest.raises(WriteOperationError):
        _conn().query("")


def test_query_rejects_invalid_json() -> None:
    with pytest.raises(WriteOperationError):
        _conn().query("not json {")


def test_query_rejects_missing_collection() -> None:
    with pytest.raises(WriteOperationError):
        _conn().query('{"db": "x"}')


def test_query_rejects_write_op() -> None:
    with pytest.raises(WriteOperationError):
        _conn().query('{"db": "x", "coll": "y", "op": "insertOne"}')


def test_guard_rejects_aggregation_out_stage() -> None:
    c = _conn()
    with pytest.raises(WriteOperationError):
        c._guard_pipeline([{"$match": {}}, {"$out": "results"}])


def test_guard_rejects_aggregation_merge_stage() -> None:
    c = _conn()
    with pytest.raises(WriteOperationError):
        c._guard_pipeline([{"$merge": {"into": "x"}}])


def test_allow_write_skips_pipeline_guard() -> None:
    c = _conn()
    c.allow_write = True
    c._guard_pipeline([{"$out": "results"}])  # no raise


def test_reject_js_operator_where() -> None:
    from connectpak.nosql.mongodb.connector import _reject_js_operators

    with pytest.raises(WriteOperationError):
        _reject_js_operators({"$where": "sleep(10000) || true"})


def test_reject_js_operator_nested_in_filter() -> None:
    from connectpak.nosql.mongodb.connector import _reject_js_operators

    with pytest.raises(WriteOperationError):
        _reject_js_operators({"status": "open", "$and": [{"$where": "true"}]})


def test_guard_pipeline_rejects_where_inside_match() -> None:
    c = _conn()
    with pytest.raises(WriteOperationError):
        c._guard_pipeline([{"$match": {"$where": "this.x > 0"}}])


def test_reject_js_operator_function() -> None:
    from connectpak.nosql.mongodb.connector import _reject_js_operators

    with pytest.raises(WriteOperationError):
        _reject_js_operators({"$expr": {"$function": {"body": "f", "args": [], "lang": "js"}}})
