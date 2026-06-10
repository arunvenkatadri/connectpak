"""End-to-end MCP integration test.

Builds a real FastMCP server around a SqliteConnector and exercises each of
the six registered tools via the MCP protocol (list_tools / call_tool).

This is the test that proves the headline vision works: a connector
correctly becomes an MCP server with the right tools, the right names, and
correct behavior under the read-only guard.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from connectpak.core.server import build_server
from connectpak.sql.sqlite.connector import SqliteConnector

EXPECTED_TOOLS = {
    "list_schemas",
    "list_tables",
    "describe_table",
    "sample_table",
    "query",
    "explain",
}


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "mcp_test.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE widgets (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL
        );
        INSERT INTO widgets (id, name, price) VALUES
            (1, 'sprocket', 1.99),
            (2, 'cog', 2.49),
            (3, 'gizmo', 9.99);
        """
    )
    conn.commit()
    conn.close()
    return str(path)


@pytest.fixture
def connector(db_path: str) -> SqliteConnector:
    c = SqliteConnector(db_path)
    yield c
    c.close()


@pytest.fixture
def server(connector: SqliteConnector):
    return build_server(connector, server_name="connectpak-sqlite-test")


def _payload(result) -> object:
    """call_tool returns (content_blocks, structured_content). The structured
    payload is what an LLM client gets back — use it for assertions."""
    content_blocks, structured = result
    if structured and "result" in structured:
        return structured["result"]
    # Fall back to parsing the first text block
    assert content_blocks, "tool returned no content"
    text = content_blocks[0].text
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


@pytest.mark.asyncio
async def test_mcp_server_registers_exactly_six_tools(server) -> None:
    tools = await server.list_tools()
    names = {t.name for t in tools}
    assert names == EXPECTED_TOOLS


@pytest.mark.asyncio
async def test_mcp_list_schemas(server) -> None:
    result = await server.call_tool("list_schemas", {})
    assert _payload(result) == ["main"]


@pytest.mark.asyncio
async def test_mcp_list_tables(server) -> None:
    result = await server.call_tool("list_tables", {})
    rows = _payload(result)
    names = [r["name"] for r in rows]
    assert "widgets" in names


@pytest.mark.asyncio
async def test_mcp_describe_table(server) -> None:
    result = await server.call_tool("describe_table", {"name": "widgets"})
    desc = _payload(result)
    assert desc["name"] == "widgets"
    assert desc["primary_key"] == ["id"]
    col_names = {c["name"] for c in desc["columns"]}
    assert col_names == {"id", "name", "price"}


@pytest.mark.asyncio
async def test_mcp_sample_table(server) -> None:
    result = await server.call_tool("sample_table", {"name": "widgets", "limit": 2})
    sample = _payload(result)
    assert sample["row_count"] == 2
    assert "price" in sample["columns"]


@pytest.mark.asyncio
async def test_mcp_query_read_only(server) -> None:
    result = await server.call_tool(
        "query", {"sql": "SELECT name FROM widgets ORDER BY id"}
    )
    out = _payload(result)
    assert out["row_count"] == 3
    assert [r[0] for r in out["rows"]] == ["sprocket", "cog", "gizmo"]


@pytest.mark.asyncio
async def test_mcp_query_rejects_writes(server) -> None:
    """The read-only guard must propagate through the MCP boundary."""
    with pytest.raises(Exception) as excinfo:
        await server.call_tool("query", {"sql": "DELETE FROM widgets"})
    msg = str(excinfo.value).lower()
    assert "delete" in msg or "read" in msg or "write" in msg


@pytest.mark.asyncio
async def test_mcp_explain_returns_text(server) -> None:
    result = await server.call_tool(
        "explain", {"sql": "SELECT * FROM widgets WHERE id = 1"}
    )
    out = _payload(result)
    assert isinstance(out, str)
    assert out.strip() != ""


@pytest.mark.asyncio
async def test_mcp_query_truncation_signal(server) -> None:
    result = await server.call_tool(
        "query", {"sql": "SELECT id FROM widgets ORDER BY id", "max_rows": 2}
    )
    out = _payload(result)
    assert out["row_count"] == 2
    assert out["truncated"] is True
