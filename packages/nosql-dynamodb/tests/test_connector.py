"""Offline tests for DynamoDBConnector. Live engine tests run separately."""

from __future__ import annotations

from connectpak.nosql.dynamodb.connector import DynamoDBConnector


def test_class_metadata() -> None:
    c = DynamoDBConnector.__new__(DynamoDBConnector)
    assert c.name == "dynamodb"
