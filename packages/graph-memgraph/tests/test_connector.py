"""Offline tests for MemgraphConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.graph.memgraph.connector import MemgraphConnector
from connectpak.graph.neo4j.connector import Neo4jConnector


def test_class_metadata() -> None:
    c = MemgraphConnector.__new__(MemgraphConnector)
    assert c.name == "memgraph"


def test_memgraph_is_a_neo4j_connector() -> None:
    """Memgraph speaks Bolt + Cypher; we inherit and only override `name`."""
    assert issubclass(MemgraphConnector, Neo4jConnector)


def test_query_rejects_write_cypher() -> None:
    c = MemgraphConnector("bolt://nobody:nope@127.0.0.1:1")
    with pytest.raises(WriteOperationError):
        c.query("CREATE (a:Node)")
