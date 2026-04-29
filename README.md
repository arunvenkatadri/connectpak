# connectpak

**MCP-native database connectors for LLMs.** Drop into Claude Desktop, Cursor,
Continue, ChatGPT — anything that speaks the [Model Context
Protocol](https://modelcontextprotocol.io/). The model can list schemas,
inspect tables, sample rows, and run read-only queries against your data.

Each engine ships as its own package so you only install what you use.

## Engines

| Track  | Engines                                                                                       |
| ------ | --------------------------------------------------------------------------------------------- |
| SQL    | postgres ✓, sqlite ✓, mysql, sqlserver, oracle, bigquery, snowflake, redshift, databricks, clickhouse |
| NoSQL  | cassandra, elasticsearch, mongodb, dynamodb                                                   |
| Graph  | neo4j, neptune, arangodb, memgraph                                                            |
| Vector | pgvector, pinecone, weaviate, qdrant, chroma, milvus                                          |

✓ = full implementation. The rest are stubs raising `NotImplementedError` —
PRs welcome (see `CONTRIBUTING.md`).

## Tool surface

Every connector exposes the same six MCP tools:

| Tool            | Purpose                                            |
| --------------- | -------------------------------------------------- |
| `list_schemas`  | List schemas / namespaces.                         |
| `list_tables`   | List tables and views, optionally scoped.          |
| `describe_table`| Columns, primary key, foreign keys, indexes.       |
| `sample_table`  | First N rows of a table.                           |
| `query`         | Run a read-only SQL query.                         |
| `explain`       | Engine `EXPLAIN` output for the given query.       |

## Safety

Read-only by default. There are two independent layers, both required:

1. **Parser guard** (`connectpak.core.guard.assert_read_only`) — sqlglot
   parses every query before it leaves the process. The whole AST is walked,
   so `WITH x AS (DELETE ...) SELECT ...` style attacks are rejected.
2. **Engine-level read-only** — Postgres opens with
   `default_transaction_read_only=on` and a session-level read-only
   characteristic; SQLite opens via `mode=ro` URI; other engines apply the
   equivalent setting.

Plus a statement timeout (default 30s) and a row cap (default 1000) on every
query.

Pass `--allow-write` only if you really mean it.

## Quick start

### Postgres

```bash
uv sync
export CONNECTPAK_POSTGRES_DSN="postgresql://user:pass@localhost:5432/mydb"
uv run connectpak-sql-postgres
```

### SQLite

```bash
uv sync
export CONNECTPAK_SQLITE_PATH="/path/to/db.sqlite"
uv run connectpak-sql-sqlite
```

Wire the resulting MCP server into your client of choice.

## Development

```bash
uv sync
uv run pytest
```

The `sql-sqlite` package is the smallest reference implementation and the
primary smoke-test target.

## License

MIT — see `LICENSE`.
