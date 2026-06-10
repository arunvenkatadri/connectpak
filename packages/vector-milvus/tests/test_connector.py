"""Offline tests for MilvusConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.vector.milvus.connector import MilvusConnector, _parse_config


def test_class_metadata() -> None:
    c = MilvusConnector.__new__(MilvusConnector)
    assert c.name == "milvus"


def test_parse_config_basic() -> None:
    p = _parse_config("http://localhost:19530")
    assert p["uri"].startswith("http://localhost")
    assert p["token"] is None


def test_parse_config_with_token() -> None:
    p = _parse_config("https://mykey@in03-xyz.api.cloud.zilliz.com")
    assert p["token"] == "mykey"


def _conn() -> MilvusConnector:
    return MilvusConnector("http://localhost:19530")


def test_parse_spec_rejects_empty() -> None:
    with pytest.raises(WriteOperationError):
        _conn()._parse_spec("")


def test_parse_spec_rejects_missing_collection() -> None:
    with pytest.raises(WriteOperationError):
        _conn()._parse_spec('{"vector": [1,2,3]}')


def test_parse_spec_accepts_valid() -> None:
    spec = _conn()._parse_spec(
        '{"collection": "docs", "vector": [1,2,3], "limit": 5}'
    )
    assert spec["collection"] == "docs"
