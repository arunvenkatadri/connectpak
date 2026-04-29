# connectpak-nosql-cassandra

Cassandra connector for connectpak.

## Quick start

```bash
uv sync
export CONNECTPAK_CASSANDRA_HOSTS="..."
uv run connectpak-nosql-cassandra
```

See the connector module docstring for the accepted config / DSN format and
for any engine-specific safety notes (engine-level read-only mode, statement
timeout mechanism, query language for the `query` tool).
