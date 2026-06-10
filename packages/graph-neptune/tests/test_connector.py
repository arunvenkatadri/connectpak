"""Offline tests for NeptuneConnector. Live engine tests run separately."""

from __future__ import annotations

import pytest
from connectpak.core.guard import WriteOperationError
from connectpak.graph.neptune.connector import NeptuneConnector


def test_class_metadata() -> None:
    c = NeptuneConnector.__new__(NeptuneConnector)
    assert c.name == "neptune"


def _conn() -> NeptuneConnector:
    return NeptuneConnector("wss://nobody:1/gremlin")


@pytest.mark.parametrize(
    "gremlin",
    [
        "g.addV('Person').property('name', 'Alice')",
        "g.V().drop()",
        "g.addE('knows').from(g.V(1)).to(g.V(2))",
        "g.V(1).property('name', 'Bob')",
    ],
)
def test_query_rejects_write_gremlin(gremlin: str) -> None:
    with pytest.raises(WriteOperationError):
        _conn().query(gremlin)
