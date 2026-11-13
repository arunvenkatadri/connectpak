# connectpak

Skills that teach Claude to explore 24 databases safely, read-only, through
the open-source connectpak MCP server: Postgres, MySQL, Snowflake, BigQuery,
MongoDB, Neo4j, Pinecone, and more. The agent lists schemas, reads table
structure and relationships, samples real values, and then runs narrow,
read-only queries in each engine's own query format.

## What it includes

Four skills: `explore-sql`, `explore-documents`, `explore-graph`, and
`explore-vector`. Each covers the workflow (orient, read the schema, sample,
query narrowly, report truncated results honestly), the query format for each
engine in its family, and how to treat database contents as data rather than
instructions.

## Setup

The skills use the connectpak MCP server, which runs on your machine. Add it
once in a terminal ([uv](https://docs.astral.sh/uv/) must be installed):

```bash
claude mcp add connectpak --scope user -e CONNECTPAK_CONNECTION="postgresql://reader:pw@localhost:5432/app" \
  -- uvx --from connectpak==0.1.1 connectpak
```

Add `-e CONNECTPAK_ENGINE=<engine>` when the engine can't be read from the
connection string:

| Database | Engine | Connection example |
| --- | --- | --- |
| Postgres | detected | `postgresql://reader:pw@db.example.com:5432/app` |
| SQLite | detected | `/Users/me/data/analytics.sqlite` |
| MySQL | detected | `mysql://reader:pw@db.example.com:3306/app` |
| ClickHouse | detected | `clickhouse://reader:pw@localhost:8123/default` |
| SQL Server | detected | `mssql://reader:pw@db.example.com:1433/app` |
| Oracle | `oracle` | `reader/pw@db.example.com:1521/ORCLPDB1` |
| BigQuery | `bigquery` | `my-gcp-project` |
| Snowflake | detected | `snowflake://user:pw@account/db/schema?warehouse=WH&role=READONLY` |
| Redshift | detected | `redshift://user:pw@host:5439/db` |
| Databricks | detected | `databricks://token:dapi-xxxxx@host.cloud.databricks.com?http_path=/sql/1.0/...` |
| MongoDB | detected | `mongodb://user:pw@host:27017/dbname` |
| DynamoDB | `dynamodb` | `us-east-1` |
| Elasticsearch | `elasticsearch` | `http://elastic:pw@localhost:9200` |
| Cassandra | `cassandra` | `user:pw@127.0.0.1:9042` |
| Neo4j | detected | `neo4j+s://neo4j:pw@cluster.example.com` |
| Memgraph | `memgraph` | `bolt://user:pw@localhost:7687` |
| ArangoDB | `arangodb` | `http://root:pw@localhost:8529/_system` |
| Amazon Neptune | detected | `wss://my-cluster.cluster-xxxx.us-east-1.neptune.amazonaws.com:8182/gremlin` |
| pgvector | `pgvector` | `postgresql://reader:pw@db.example.com:5432/app` |
| Pinecone | `pinecone` | `pcsk_xxxxx` |
| Weaviate | `weaviate` | `https://my-cluster.weaviate.network` |
| Qdrant | `qdrant` | `https://api-key@my-cluster.qdrant.io` |
| Chroma | `chroma` | `http://localhost:8000` |
| Milvus | `milvus` | `http://localhost:19530` |

BigQuery uses Google Application Default Credentials. DynamoDB uses the
standard AWS credential chain. Use read-only database credentials.

## What it runs, sends, and fetches

- **This plugin** contains only Markdown skills, a manifest, and icons. It
  runs nothing by itself.
- **The server you add** runs `uvx --from connectpak==0.1.1 connectpak`.
  On first start uv downloads that exact version of the `connectpak` package
  and its database drivers from PyPI. Its source is at https://github.com/arunvenkatadri/connectpak.
- **Connects to:** only the database in your connection string, using that
  database's official driver.
- **Sends:** query results go to Claude in your session. connectpak has no
  telemetry and sends data nowhere else.
- **Stores:** nothing. `claude mcp add` keeps the connection string in your
  Claude Code configuration.

## Safety

Read-only is enforced twice: by a query guard (a full SQL parse for SQL
engines, whitelisted operations for document and vector stores, and a
write-keyword screen for graph languages) and by the engine's own read-only
mode. Every query has a 30-second timeout and a 1,000-row cap.

Source, issues, and security reports: https://github.com/arunvenkatadri/connectpak. MIT licensed.
