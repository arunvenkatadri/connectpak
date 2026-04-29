# connectpak-vector-pgvector

[pgvector](https://github.com/pgvector/pgvector) connector for connectpak.
Thin layer over `connectpak-sql-postgres` that reports the real
`vector(N)` type for vector columns instead of the bare `USER-DEFINED`
string the standard `information_schema` returns.

## Quick start

```bash
uv sync
export CONNECTPAK_PGVECTOR_DSN="postgresql://user:pass@localhost:5432/mydb"
uv run connectpak-vector-pgvector
```

The connection inherits Postgres' two-layer read-only setup. Vector queries
work through the standard `query` tool — for example:

```sql
SELECT id, embedding <=> '[0.1, 0.2, 0.3]'::vector AS distance
FROM items
ORDER BY distance
LIMIT 5
```

The pgvector extension does not need to be loaded by the connector — if the
database has it installed, it just works.
