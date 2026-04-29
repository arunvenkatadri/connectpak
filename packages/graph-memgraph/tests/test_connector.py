"""Offline tests for MemgraphConnector. Live engine tests run separately."""

from __future__ import annotations

from connectpak.graph.memgraph.connector import MemgraphConnector


def test_class_metadata() -> None:
    c = MemgraphConnector.__new__(MemgraphConnector)
    assert c.name == "memgraph"
