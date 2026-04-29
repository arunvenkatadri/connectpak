# connectpak-sql-snowflake

Snowflake connector for connectpak.

## Quick start

```bash
uv sync
export CONNECTPAK_SNOWFLAKE_DSN="..."
uv run connectpak-sql-snowflake
```

See the connector module docstring for the accepted config / DSN format and
for any engine-specific safety notes (engine-level read-only mode, statement
timeout mechanism, query language for the `query` tool).
