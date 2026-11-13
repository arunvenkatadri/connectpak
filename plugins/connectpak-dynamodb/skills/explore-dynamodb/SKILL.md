---
name: explore-dynamodb
description: Use when the user asks about data, tables, or schema in their DynamoDB database, or wants a question answered from it. Explores and queries DynamoDB read-only through the connectpak dynamodb MCP tools.
---

# Explore DynamoDB with connectpak

The `dynamodb` MCP server from this plugin exposes six read-only tools:
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
{"op": "scan", "table": "Users"}
{"op": "query", "TableName": "Orders", "KeyConditionExpression": "uid = :u",
 "ExpressionAttributeValues": {":u": {"S": "alice"}}}
{"op": "get_item", "table": "Users", "key": {"id": "alice"}}
{"op": "execute_statement", "statement": "SELECT * FROM Users WHERE id = 'alice'"}
```
PartiQL statements are screened by the SQL parser guard.

## Read-only by design

Every write is rejected twice: by the parser guard and by the engine's own
read-only mode. Each query also has a statement timeout (default 30s). If
the user asks for a change (insert, update, delete, DDL), explain that this
connection is read-only and offer the statement for them to run themselves.
Never try to work around the guard.

## If the tools are missing or fail to start

The server needs `$CONNECTPAK_DYNAMODB_REGION` (example: `us-east-1`).

- **Claude Code:** run `/plugin`, open `connectpak-dynamodb`, and set the
  connection, then restart the session.
- **Codex:** export `CONNECTPAK_DYNAMODB_REGION` in the shell, then restart Codex.

The server is launched with `uvx`, so `uv` must be installed and on `PATH`.
