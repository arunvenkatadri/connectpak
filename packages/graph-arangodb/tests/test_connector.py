"""Offline tests for ArangoDBConnector. Live engine tests run separately."""

from __future__ import annotations

from connectpak.graph.arangodb.connector import ArangoDBConnector


def test_class_metadata() -> None:
    c = ArangoDBConnector.__new__(ArangoDBConnector)
    assert c.name == "arangodb"
