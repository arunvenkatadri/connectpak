"""Offline tests for ElasticsearchConnector. Live engine tests run separately."""

from __future__ import annotations

from connectpak.nosql.elasticsearch.connector import ElasticsearchConnector


def test_class_metadata() -> None:
    c = ElasticsearchConnector.__new__(ElasticsearchConnector)
    assert c.name == "elasticsearch"
