"""Offline tests for CassandraConnector. Live engine tests run separately."""

from __future__ import annotations

from connectpak.nosql.cassandra.connector import CassandraConnector


def test_class_metadata() -> None:
    c = CassandraConnector.__new__(CassandraConnector)
    assert c.name == "cassandra"
