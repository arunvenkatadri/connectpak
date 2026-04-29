"""Offline tests for ChromaConnector. Live engine tests run separately."""

from __future__ import annotations

from connectpak.vector.chroma.connector import ChromaConnector


def test_class_metadata() -> None:
    c = ChromaConnector.__new__(ChromaConnector)
    assert c.name == "chroma"
