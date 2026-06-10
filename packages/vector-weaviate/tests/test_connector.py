"""Offline tests for WeaviateConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.vector.weaviate.connector import WeaviateConnector


def test_class_metadata() -> None:
    c = WeaviateConnector.__new__(WeaviateConnector)
    assert c.name == "weaviate"


def _conn() -> WeaviateConnector:
    return WeaviateConnector("http://localhost:8080")


def test_parse_spec_rejects_empty() -> None:
    with pytest.raises(WriteOperationError):
        _conn()._parse_spec("")


def test_parse_spec_rejects_missing_collection() -> None:
    with pytest.raises(WriteOperationError):
        _conn()._parse_spec('{"near_vector": [1,2,3]}')


def test_parse_spec_accepts_valid() -> None:
    spec = _conn()._parse_spec(
        '{"collection": "Article", "near_vector": [1,2,3], "limit": 10}'
    )
    assert spec["collection"] == "Article"
