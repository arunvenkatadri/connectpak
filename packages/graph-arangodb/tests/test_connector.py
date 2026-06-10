"""Offline tests for ArangoDBConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.graph.arangodb.connector import ArangoDBConnector, _parse_config


def test_class_metadata() -> None:
    c = ArangoDBConnector.__new__(ArangoDBConnector)
    assert c.name == "arangodb"


def test_parse_config_full() -> None:
    p = _parse_config("http://root:pass@arangodb:8529/mydb")
    assert p["host"] == "http://arangodb:8529"
    assert p["username"] == "root"
    assert p["password"] == "pass"
    assert p["database"] == "mydb"


def test_parse_config_defaults() -> None:
    p = _parse_config("http://localhost")
    assert p["database"] == "_system"
    assert p["username"] == "root"


@pytest.mark.parametrize(
    "aql",
    [
        "INSERT { a: 1 } INTO things",
        "UPDATE 'k' WITH { x: 1 } IN things",
        "REPLACE 'k' WITH { x: 1 } IN things",
        "REMOVE 'k' IN things",
        "UPSERT { _key: 'k' } INSERT {} UPDATE {} IN things",
    ],
)
def test_query_rejects_write_aql(aql: str) -> None:
    c = ArangoDBConnector("http://root:@127.0.0.1:1/_system")
    with pytest.raises(WriteOperationError):
        c.query(aql)
