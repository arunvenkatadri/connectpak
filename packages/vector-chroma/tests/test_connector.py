"""Offline tests for ChromaConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.vector.chroma.connector import ChromaConnector


def test_class_metadata() -> None:
    c = ChromaConnector.__new__(ChromaConnector)
    assert c.name == "chroma"


def _conn() -> ChromaConnector:
    return ChromaConnector("http://localhost:8000")


def test_parse_spec_rejects_empty() -> None:
    with pytest.raises(WriteOperationError):
        _conn()._parse_spec("")


def test_parse_spec_rejects_missing_collection() -> None:
    with pytest.raises(WriteOperationError):
        _conn()._parse_spec('{"query_embeddings": [[1,2,3]]}')


def test_parse_spec_accepts_valid() -> None:
    spec = _conn()._parse_spec(
        '{"collection": "docs", "query_embeddings": [[1,2,3]], "n_results": 5}'
    )
    assert spec["collection"] == "docs"
