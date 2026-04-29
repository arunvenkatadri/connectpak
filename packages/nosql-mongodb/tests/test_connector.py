"""Offline tests for MongoDBConnector. Live engine tests run separately."""

from __future__ import annotations

from connectpak.nosql.mongodb.connector import MongoDBConnector


def test_class_metadata() -> None:
    c = MongoDBConnector.__new__(MongoDBConnector)
    assert c.name == "mongodb"
