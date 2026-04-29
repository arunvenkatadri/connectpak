# connectpak-sql-redshift

Redshift connector for connectpak.

## Quick start

```bash
uv sync
export CONNECTPAK_REDSHIFT_DSN="..."
uv run connectpak-sql-redshift
```

See the connector module docstring for the accepted config / DSN format and
for any engine-specific safety notes (engine-level read-only mode, statement
timeout mechanism, query language for the `query` tool).
