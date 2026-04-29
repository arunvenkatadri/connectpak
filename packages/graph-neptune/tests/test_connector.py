"""Offline tests for NeptuneConnector. Live engine tests run separately."""

from __future__ import annotations

from connectpak.graph.neptune.connector import NeptuneConnector


def test_class_metadata() -> None:
    c = NeptuneConnector.__new__(NeptuneConnector)
    assert c.name == "neptune"
