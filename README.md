# connectpak

![connectpak — LLM database connector. Let LLMs talk to your databases.](docs/assets/connectpak-banner.png)

**MCP-native database connectors for LLMs.** Drop into Claude Desktop, Cursor,
Continue, ChatGPT — anything that speaks the [Model Context
Protocol](https://modelcontextprotocol.io/). The model can list schemas,
inspect tables, sample rows, and run read-only queries against your data.

Each engine ships as its own package so you only install what you use.

## Engines

| Track  | Engines                                                                                                |
| ------ | ------------------------------------------------------------------------------------------------------ |
| SQL    | postgres ✓, sqlite ✓, mysql ✓, clickhouse ✓, sqlserver ✓, oracle ✓, bigquery ✓, snowflake ✓, redshift ✓, databricks ✓ |
| NoSQL  | mongodb ✓, dynamodb ✓, elasticsearch ✓, cassandra ✓                                                    |
| Graph  | neo4j ✓, memgraph ✓, arangodb ✓, neptune ✓                                                             |
| Vector | pgvector ✓, pinecone ✓, weaviate ✓, qdrant ✓, chroma ✓, milvus ✓                                       |

✓ = full implementation.

For SQL engines, `query` accepts SQL and is guarded by a sqlglot parser
that walks the full AST. For non-SQL engines (NoSQL, graph, vector), the
`query` tool accepts the engine's native form: a JSON spec for document
and vector stores; raw Cypher / CQL / AQL / Gremlin for graph engines
(with a write-keyword guard). See each connector's module docstring for
the exact format.

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
   so writes hiding inside an otherwise-allowed shape are rejected too:
   `WITH x AS (DELETE ...) SELECT ...`, `SELECT ... INTO t`, row-locking
   reads (`FOR UPDATE` / `FOR SHARE`), and mutating `PRAGMA` setters. The
   graph and wide-column languages (Cypher, CQL, AQL, Gremlin) are screened
   for write keywords; MongoDB additionally blocks server-side-JavaScript
   operators (`$where`, `$function`).
2. **Engine-level read-only** — Postgres opens with
   `default_transaction_read_only=on` and a session-level read-only
   characteristic; SQLite opens via `mode=ro` URI; other engines apply the
   equivalent setting.

Plus a statement timeout (default 30s) and a row cap (default 1000) on every
query. Identifiers passed to `sample_table` are quoted with engine-specific
escaping (or parameterized).

Pass `--allow-write` only if you really mean it, and always point the DSN at
a read-only database role — see `SECURITY.md`.

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

### MySQL

```bash
uv sync
export CONNECTPAK_MYSQL_DSN="mysql://user:pass@localhost:3306/mydb"
uv run connectpak-sql-mysql
```

### ClickHouse

```bash
uv sync
export CONNECTPAK_CLICKHOUSE_DSN="clickhouse://default:@localhost:8123/default"
uv run connectpak-sql-clickhouse
```

### pgvector

```bash
uv sync
export CONNECTPAK_PGVECTOR_DSN="postgresql://user:pass@localhost:5432/mydb"
uv run connectpak-vector-pgvector
```

For the other engines, see each package's `README.md` and connector module
docstring for the accepted config / DSN format. The CLI is the same shape:
`uv run connectpak-<track>-<engine>` reading from the matching
`CONNECTPAK_<ENGINE>_*` env var.

Wire the resulting MCP server into your client of choice — see
`docs/clients/claude-desktop.md` and `docs/clients/cursor.md` for ready-made
config snippets. For the JSON `query` formats accepted by the document,
graph, and vector engines, see `docs/query-formats.md`.

## Development

```bash
uv sync
uv run pytest          # 177 tests across the suite
uv run ruff check .    # lint
```

The `sql-sqlite` package is the smallest reference implementation and the
primary smoke-test target. End-to-end MCP integration tests in
`packages/core/tests/test_mcp_integration.py` exercise the full
connector → FastMCP → tool-invocation path against a real SQLite fixture.

## License

MIT — see `LICENSE`.
