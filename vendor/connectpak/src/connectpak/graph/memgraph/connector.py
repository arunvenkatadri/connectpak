"""Memgraph connector.

Memgraph speaks the Bolt protocol and most of Cypher, so this is a thin
subclass of `Neo4jConnector`. The default Bolt port is 7687, the same as
Neo4j; pass the URI in `config`.

Config: bolt://user:pass@host:7687
"""

from __future__ import annotations

from connectpak.graph.neo4j.connector import Neo4jConnector


class MemgraphConnector(Neo4jConnector):
    name = "memgraph"
