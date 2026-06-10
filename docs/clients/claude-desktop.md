# Using connectpak with Claude Desktop

Claude Desktop reads MCP server configuration from
`claude_desktop_config.json`. Add a `mcpServers` entry pointing at any
connectpak CLI:

```json
{
  "mcpServers": {
    "my-postgres": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/connectpak",
        "connectpak-sql-postgres"
      ],
      "env": {
        "CONNECTPAK_POSTGRES_DSN": "postgresql://reader:pw@db.example.com:5432/app"
      }
    },
    "my-sqlite": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/connectpak",
        "connectpak-sql-sqlite"
      ],
      "env": {
        "CONNECTPAK_SQLITE_PATH": "/Users/me/data/analytics.sqlite"
      }
    }
  }
}
```

The file location:
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

After editing, restart Claude Desktop. The six tools (`list_schemas`,
`list_tables`, `describe_table`, `sample_table`, `query`, `explain`) will
appear in the tool picker.

## Tips

- Use a **read-only database role** for the DSN. The connector enforces
  read-only twice (parser guard + engine-level), but defense-in-depth
  matters.
- Set `--statement-timeout-ms` if you want the model to fail fast on
  expensive queries:
  ```json
  "args": ["run", "...", "connectpak-sql-postgres",
           "--statement-timeout-ms", "10000"]
  ```
- The model gets back a `truncated: true` flag when results hit the row
  cap; it can re-issue with `max_rows` if it really needs more.

## Multiple databases

You can register the same engine multiple times under different names —
one Claude Desktop server per environment is a common pattern.
