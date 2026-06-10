"""Offline tests for Neo4jConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError, assert_no_write_keywords
from connectpak.graph.neo4j.connector import (
    _CYPHER_WRITE_KEYWORDS,
    Neo4jConnector,
    _parse_config,
)


def test_class_metadata() -> None:
    c = Neo4jConnector.__new__(Neo4jConnector)
    assert c.name == "neo4j"


def test_parse_config_full() -> None:
    p = _parse_config("bolt://neo4j:secret@db.example.com:7687")
    assert p["uri"] == "bolt://db.example.com:7687"
    assert p["auth"] == ("neo4j", "secret")


def test_parse_config_no_auth() -> None:
    p = _parse_config("bolt://localhost")
    assert p["auth"] is None
    assert "localhost" in p["uri"]


@pytest.mark.parametrize(
    "cypher",
    [
        "CREATE (a:Person {name: 'Alice'})",
        "MATCH (n) DELETE n",
        "MATCH (n) SET n.x = 1",
        "MATCH (n) REMOVE n.x",
        "MERGE (n:Person {id: 1})",
        "MATCH (n) DETACH DELETE n",
    ],
)
def test_query_rejects_write_cypher(cypher: str) -> None:
    c = Neo4jConnector("bolt://nobody:nope@127.0.0.1:1")
    with pytest.raises(WriteOperationError):
        c.query(cypher)


def test_keyword_guard_accepts_read_cypher() -> None:
    # MATCH ... RETURN must pass.
    assert_no_write_keywords(
        "MATCH (n:Person) RETURN n LIMIT 10", _CYPHER_WRITE_KEYWORDS
    )
