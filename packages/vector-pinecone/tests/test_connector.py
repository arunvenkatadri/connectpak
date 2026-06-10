"""Offline tests for PineconeConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.vector.pinecone.connector import PineconeConnector


def test_class_metadata() -> None:
    c = PineconeConnector.__new__(PineconeConnector)
    assert c.name == "pinecone"


def _conn() -> PineconeConnector:
    return PineconeConnector("fake-api-key")


def test_parse_spec_rejects_empty() -> None:
    with pytest.raises(WriteOperationError):
        _conn()._parse_spec("")


def test_parse_spec_rejects_non_json() -> None:
    with pytest.raises(WriteOperationError):
        _conn()._parse_spec("not json")


def test_parse_spec_rejects_missing_index() -> None:
    with pytest.raises(WriteOperationError):
        _conn()._parse_spec('{"vector": [1,2,3], "top_k": 5}')


def test_parse_spec_accepts_valid() -> None:
    spec = _conn()._parse_spec('{"index": "items", "vector": [1,2,3], "top_k": 5}')
    assert spec["index"] == "items"
    assert spec["top_k"] == 5
