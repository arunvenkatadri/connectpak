"""Offline tests for WeaviateConnector. Live engine tests run separately."""

from __future__ import annotations

from connectpak.vector.weaviate.connector import WeaviateConnector


def test_class_metadata() -> None:
    c = WeaviateConnector.__new__(WeaviateConnector)
    assert c.name == "weaviate"
