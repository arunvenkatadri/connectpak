# Query formats by engine

Every connector implements the same six MCP tools, but the `query` tool's
input format varies because the engines themselves don't all speak SQL.

## SQL engines

`query` takes a SQL string. Dialect is whatever the engine speaks. The
parser guard uses [sqlglot](https://github.com/tobymao/sqlglot) to walk
the full AST and reject any state-mutating node.

| Engine    | `query` input              | Dialect    |
| --------- | -------------------------- | ---------- |
| postgres  | SQL string                 | postgres   |
| sqlite    | SQL string                 | sqlite     |
| mysql     | SQL string                 | mysql      |
| clickhouse| SQL string                 | clickhouse |
| sqlserver | SQL string                 | tsql       |
| oracle    | SQL string                 | oracle     |
| bigquery  | SQL string                 | bigquery   |
| snowflake | SQL string                 | snowflake  |
| redshift  | SQL string                 | redshift   |
| databricks| SQL string                 | databricks |
| pgvector  | SQL string (incl. `<=>`)   | postgres   |

## Graph engines

`query` takes a query in the engine's native graph language. Read-only
is enforced by keyword-level scanning (see `assert_no_write_keywords` —
less robust than the SQL AST walk; a write keyword inside a string
literal can false-positive).

| Engine    | `query` input  | Forbidden keywords                                |
| --------- | -------------- | ------------------------------------------------- |
| neo4j     | Cypher         | CREATE, MERGE, DELETE, REMOVE, SET, DROP, DETACH, FOREACH, LOAD |
| memgraph  | Cypher         | (same as neo4j)                                   |
| arangodb  | AQL            | INSERT, UPDATE, REPLACE, REMOVE, UPSERT           |
| neptune   | Gremlin string | addV, addE, drop, property                        |

## Document / KV / search engines

`query` takes a JSON spec. The `op` field is whitelisted.

### MongoDB
```json
{"db": "store", "coll": "orders", "op": "find",
 "filter": {"status": "open"}, "projection": {"_id": 0, "total": 1}}
```
or
```json
{"db": "store", "coll": "orders", "op": "aggregate",
 "pipeline": [{"$match": {"total": {"$gt": 100}}}, {"$count": "n"}]}
```
The aggregation pipeline guard rejects `$out`, `$merge`, `$indexStats`.

### DynamoDB
```json
{"op": "scan", "table": "Users"}
{"op": "query", "TableName": "Orders", "KeyConditionExpression": "uid = :u",
 "ExpressionAttributeValues": {":u": {"S": "alice"}}}
{"op": "get_item", "table": "Users", "key": {"id": "alice"}}
{"op": "execute_statement", "statement": "SELECT * FROM Users WHERE id = 'alice'"}
```
PartiQL statements are screened by the SQL parser guard.

### Elasticsearch
```json
{"op": "search", "index": "logs", "body": {"query": {"match_all": {}}}, "size": 10}
{"op": "count",  "index": "logs", "body": {"query": {"term": {"level": "ERROR"}}}}
{"op": "sql",    "query": "SELECT * FROM logs WHERE level = 'ERROR' LIMIT 10"}
{"op": "esql",   "query": "FROM logs | WHERE level == \"ERROR\" | LIMIT 10"}
```

### Cassandra
`query` takes raw CQL with a keyword guard.
```cql
SELECT id, total FROM store.orders WHERE user_id = ? LIMIT 100
```

## Vector engines

`query` takes a JSON spec. The fields differ per engine but always
include `collection` (or its equivalent).

### Pinecone
```json
{"index": "items", "vector": [0.1, 0.2, 0.3], "top_k": 10,
 "filter": {"category": "books"}, "namespace": "prod",
 "include_metadata": true}
```

### Qdrant
```json
{"collection": "items", "vector": [0.1, 0.2, 0.3], "limit": 10,
 "filter": {"must": [{"key": "stock", "match": {"value": "in"}}]},
 "with_payload": true}
```

### Weaviate
```json
{"collection": "Article", "near_vector": [0.1, 0.2, 0.3], "limit": 10}
{"collection": "Article", "near_text": "machine learning", "limit": 10}
```

### Chroma
```json
{"collection": "docs", "query_embeddings": [[0.1, 0.2, 0.3]], "n_results": 5,
 "where": {"source": "wiki"}}
{"collection": "docs", "query_texts": ["who is alice?"], "n_results": 5}
```

### Milvus
```json
{"collection": "docs", "vector": [0.1, 0.2, 0.3], "limit": 5,
 "anns_field": "embedding", "output_fields": ["id", "title"],
 "filter": "year > 2020"}
```

For scalar-only filtering (no vector search):
```json
{"collection": "docs", "filter": "id > 100", "limit": 50,
 "output_fields": ["id", "title"]}
```
