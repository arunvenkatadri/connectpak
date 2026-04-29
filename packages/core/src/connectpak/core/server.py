"""MCP server runner.

Wraps a BaseConnector instance in a FastMCP server exposing six tools.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from connectpak.core.base import BaseConnector


def _to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, list):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, tuple):
        return [_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    return obj


def build_server(connector: BaseConnector, server_name: str | None = None):
    """Build a FastMCP server registering six tools wrapping the connector."""
    from mcp.server.fastmcp import FastMCP

    name = server_name or f"connectpak-{connector.name}"
    mcp = FastMCP(name)

    @mcp.tool()
    def list_schemas() -> list[str]:
        """List schemas / namespaces visible to the connector."""
        return connector.list_schemas()

    @mcp.tool()
    def list_tables(schema: str | None = None) -> list[dict[str, Any]]:
        """List tables (and views) in the given schema, or all schemas if omitted."""
        return [{"schema": s, "name": n} for s, n in connector.list_tables(schema=schema)]

    @mcp.tool()
    def describe_table(name: str, schema: str | None = None) -> dict[str, Any]:
        """Return columns, primary key, foreign keys, and indexes for a table."""
        return _to_jsonable(connector.describe_table(name=name, schema=schema))

    @mcp.tool()
    def sample_table(
        name: str, schema: str | None = None, limit: int = 10
    ) -> dict[str, Any]:
        """Sample up to `limit` rows from the given table."""
        return _to_jsonable(connector.sample_table(name=name, schema=schema, limit=limit))

    @mcp.tool()
    def query(sql: str, max_rows: int | None = None) -> dict[str, Any]:
        """Run a read-only SQL query. Mutating statements are rejected."""
        return _to_jsonable(connector.query(sql=sql, max_rows=max_rows))

    @mcp.tool()
    def explain(sql: str) -> str:
        """Return the engine's EXPLAIN output for the given query."""
        return connector.explain(sql=sql)

    return mcp


def serve(connector: BaseConnector) -> None:
    """Build and run the MCP server, closing the connector on shutdown."""
    mcp = build_server(connector)
    try:
        mcp.run()
    finally:
        connector.close()
