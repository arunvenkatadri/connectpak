"""Offline tests for QdrantConnector. Live engine tests run separately."""

from __future__ import annotations

from connectpak.vector.qdrant.connector import QdrantConnector


def test_class_metadata() -> None:
    c = QdrantConnector.__new__(QdrantConnector)
    assert c.name == "qdrant"
