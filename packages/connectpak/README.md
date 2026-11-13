# connectpak

One command that serves any of connectpak's 24 read-only database connectors
over MCP. It installs every engine package and picks the engine from the
connection string.

```bash
CONNECTPAK_CONNECTION="postgresql://reader:pw@localhost:5432/app" uvx connectpak
CONNECTPAK_ENGINE=bigquery CONNECTPAK_CONNECTION=my-gcp-project uvx connectpak
uvx connectpak --list-engines
```

Engines detected from the connection string: Postgres, MySQL/MariaDB,
ClickHouse, SQL Server, Snowflake, Redshift, Databricks, MongoDB, Neo4j,
SQLite (a `.db`/`.sqlite` path, or a SQLAlchemy-style `sqlite:///relative.db` / `sqlite:////absolute.db` URL), and Neptune. For the others
(Oracle, BigQuery, DynamoDB, Elasticsearch, Cassandra, Memgraph, ArangoDB,
pgvector, Pinecone, Weaviate, Qdrant, Chroma, Milvus), set
`CONNECTPAK_ENGINE`. If `CONNECTPAK_CONNECTION` isn't set, the engine's own
variable (such as `CONNECTPAK_POSTGRES_DSN`) is used.

To install only one engine, use its own package instead, such as
`connectpak-sql-postgres`. See the
[main README](https://github.com/arunvenkatadri/connectpak) for the safety
model and query formats.
