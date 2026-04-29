"""Offline tests for MilvusConnector. Live engine tests run separately."""

from __future__ import annotations

from connectpak.vector.milvus.connector import MilvusConnector


def test_class_metadata() -> None:
    c = MilvusConnector.__new__(MilvusConnector)
    assert c.name == "milvus"
