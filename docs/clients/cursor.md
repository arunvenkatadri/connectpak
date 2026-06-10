# Using connectpak with Cursor

Cursor reads MCP servers from `~/.cursor/mcp.json` (or per-project from
`.cursor/mcp.json`). The shape is the same as Claude Desktop:

```json
{
  "mcpServers": {
    "analytics-db": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/connectpak",
        "connectpak-sql-postgres"
      ],
      "env": {
        "CONNECTPAK_POSTGRES_DSN": "postgresql://reader:pw@db.example.com:5432/analytics"
      }
    }
  }
}
```

Reload Cursor's window after editing. The six tools then become available
to the AI assistant.

## Per-project servers

A `.cursor/mcp.json` checked into a repo lets every contributor get the
same MCP setup. Combined with a `.env`-style file you can keep DSNs out
of the JSON itself.
