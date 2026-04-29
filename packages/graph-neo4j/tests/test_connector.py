"""Offline tests for Neo4jConnector. Live engine tests run separately."""

from __future__ import annotations

from connectpak.graph.neo4j.connector import Neo4jConnector


def test_class_metadata() -> None:
    c = Neo4jConnector.__new__(Neo4jConnector)
    assert c.name == "neo4j"
