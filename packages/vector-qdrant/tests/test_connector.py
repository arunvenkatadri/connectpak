"""Offline tests for QdrantConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.vector.qdrant.connector import QdrantConnector, _parse_config


def test_class_metadata() -> None:
    c = QdrantConnector.__new__(QdrantConnector)
    assert c.name == "qdrant"


def test_parse_config_basic() -> None:
    p = _parse_config("http://localhost:6333")
    assert p["url"] == "http://localhost:6333"
    assert p["api_key"] is None


def test_parse_config_with_api_key() -> None:
    p = _parse_config("https://mykey@cluster.qdrant.io")
    assert p["api_key"] == "mykey"
    assert p["url"].startswith("https://")


def _conn() -> QdrantConnector:
    return QdrantConnector("http://localhost:6333")


def test_parse_spec_rejects_empty() -> None:
    with pytest.raises(WriteOperationError):
        _conn()._parse_spec("")


def test_parse_spec_rejects_missing_collection() -> None:
    with pytest.raises(WriteOperationError):
        _conn()._parse_spec('{"vector": [1,2,3]}')


def test_parse_spec_accepts_valid() -> None:
    spec = _conn()._parse_spec(
        '{"collection": "items", "vector": [1,2,3], "limit": 5}'
    )
    assert spec["collection"] == "items"
