"""Offline tests for PineconeConnector. Live engine tests run separately."""

from __future__ import annotations

from connectpak.vector.pinecone.connector import PineconeConnector


def test_class_metadata() -> None:
    c = PineconeConnector.__new__(PineconeConnector)
    assert c.name == "pinecone"
