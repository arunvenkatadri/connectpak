---
name: explore-weaviate
description: Use when the user asks about data, tables, or schema in their Weaviate database, or wants a question answered from it. Explores and queries Weaviate read-only through the connectpak weaviate MCP tools.
---

# Explore Weaviate with connectpak

The `weaviate` MCP server from this plugin exposes six read-only tools:
`list_schemas`, `list_tables`, `describe_table`, `sample_table`, `query`,
and `explain`.

## Workflow

1. **Orient.** Call `list_schemas`, then `list_tables` (pass `schema` to
   narrow it). Don't guess table names.
2. **Read the schema before querying.** Call `describe_table` on every table
   you plan to touch. Use its foreign keys to work out joins instead of
   inferring them from column names.
3. **Look at real values.** Call `sample_table` when you need to know value
   formats, enums, or units before filtering on them.
4. **Query narrowly.** Select only the columns you need and filter early.
   For anything that might scan a large table, call `explain` first.
5. **Report honestly.** If a result has `truncated: true`, the row cap
   (default 1000) cut it off. Say so, then aggregate or filter instead of
   presenting partial rows as complete.

## Query format

`query` takes a JSON spec (a JSON object, passed as a string):

```json
{"collection": "Article", "near_vector": [0.1, 0.2, 0.3], "limit": 10}
{"collection": "Article", "near_text": "machine learning", "limit": 10}
```

## Read-only by design

Every write is rejected twice: by the parser guard and by the engine's own
read-only mode. Each query also has a statement timeout (default 30s). If
the user asks for a change (insert, update, delete, DDL), explain that this
connection is read-only and offer the statement for them to run themselves.
Never try to work around the guard.

## If the tools are missing or fail to start

The server needs `$CONNECTPAK_WEAVIATE_URL` (example: `https://my-cluster.weaviate.network`).

- **Claude Code:** run `/plugin`, open `connectpak-weaviate`, and set the
  connection, then restart the session.
- **Codex:** export `CONNECTPAK_WEAVIATE_URL` in the shell, then restart Codex.

The server is launched with `uvx`, so `uv` must be installed and on `PATH`.
