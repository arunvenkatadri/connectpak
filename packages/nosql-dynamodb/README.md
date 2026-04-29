# connectpak-nosql-dynamodb

DynamoDB connector for connectpak.

## Quick start

```bash
uv sync
export CONNECTPAK_DYNAMODB_REGION="..."
uv run connectpak-nosql-dynamodb
```

See the connector module docstring for the accepted config / DSN format and
for any engine-specific safety notes (engine-level read-only mode, statement
timeout mechanism, query language for the `query` tool).
