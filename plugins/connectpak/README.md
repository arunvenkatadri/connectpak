# connectpak

Read-only access to 24 databases for Claude and other AI agents, over the
Model Context Protocol (MCP). Point it at a database and the agent can list
schemas, describe tables, sample rows, and run queries. It can't change
anything: every write is rejected before it reaches the database and again
by the database's own read-only mode.

## Setup

Install the plugin, then set two options:

- **Connection string** (required, stored in your OS credential store): the
  DSN, URL, file path, or key for your database. Use read-only credentials.
- **Engine** (optional): only needed when the engine can't be read from the
  connection string. See the table.

`uv` must be installed (https://docs.astral.sh/uv/).

| Database | Engine | How it's chosen | Connection example |
| --- | --- | --- | --- |
| Postgres | `postgres` | detected | `postgresql://reader:pw@db.example.com:5432/app` |
| SQLite | `sqlite` | detected | `/Users/me/data/analytics.sqlite` |
| MySQL | `mysql` | detected | `mysql://reader:pw@db.example.com:3306/app` |
| ClickHouse | `clickhouse` | detected | `clickhouse://reader:pw@localhost:8123/default` |
| SQL Server | `sqlserver` | detected | `mssql://reader:pw@db.example.com:1433/app` |
| Oracle | `oracle` | set Engine | `reader/pw@db.example.com:1521/ORCLPDB1` |
| BigQuery | `bigquery` | set Engine | `my-gcp-project` |
| Snowflake | `snowflake` | detected | `snowflake://user:pw@account/db/schema?warehouse=WH&role=READONLY` |
| Redshift | `redshift` | detected | `redshift://user:pw@host:5439/db` |
| Databricks | `databricks` | detected | `databricks://token:dapi-xxxxx@host.cloud.databricks.com?http_path=/sql/1.0/...` |
| MongoDB | `mongodb` | detected | `mongodb://user:pw@host:27017/dbname` |
| DynamoDB | `dynamodb` | set Engine | `us-east-1` |
| Elasticsearch | `elasticsearch` | set Engine | `http://elastic:pw@localhost:9200` |
| Cassandra | `cassandra` | set Engine | `user:pw@127.0.0.1:9042` |
| Neo4j | `neo4j` | detected | `neo4j+s://neo4j:pw@cluster.example.com` |
| Memgraph | `memgraph` | set Engine | `bolt://user:pw@localhost:7687` |
| ArangoDB | `arangodb` | set Engine | `http://root:pw@localhost:8529/_system` |
| Amazon Neptune | `neptune` | detected | `wss://my-cluster.cluster-xxxx.us-east-1.neptune.amazonaws.com:8182/gremlin` |
| pgvector | `pgvector` | set Engine | `postgresql://reader:pw@db.example.com:5432/app` |
| Pinecone | `pinecone` | set Engine | `pcsk_xxxxx` |
| Weaviate | `weaviate` | set Engine | `https://my-cluster.weaviate.network` |
| Qdrant | `qdrant` | set Engine | `https://api-key@my-cluster.qdrant.io` |
| Chroma | `chroma` | set Engine | `http://localhost:8000` |
| Milvus | `milvus` | set Engine | `http://localhost:19530` |

BigQuery uses Google Application Default Credentials. DynamoDB uses the
standard AWS credential chain.

## What it includes

- An MCP server named `connectpak` with six tools: `list_schemas`,
  `list_tables`, `describe_table`, `sample_table`, `query`, and `explain`.
- Four skills that teach the agent a safe workflow (orient, read the schema,
  sample, query narrowly) and each engine's query format: `explore-sql`,
  `explore-documents`, `explore-graph`, and `explore-vector`.

## What it runs, sends, and fetches

- **Runs:** `uvx --from connectpak==0.1.1 connectpak`. On first start, uv
  downloads the `connectpak` package at that exact version, and its
  dependencies (the database drivers), from PyPI. It's cached after that.
- **Connects to:** only the database in your connection string, using that
  database's official driver.
- **Sends:** query results go to the agent in your session. connectpak has no
  telemetry, and it doesn't send data anywhere else.
- **Stores:** nothing. The connection string is kept by Claude Code in your
  OS credential store.

## Safety

Read-only is enforced twice: by a query guard (a full SQL parse for SQL
engines, whitelisted operations for document and vector stores, and a
write-keyword screen for graph languages) and by the engine's own read-only
mode. Every query has a 30-second timeout and a 1,000-row cap. Use a
database role that can only read anyway.

Source, issues, and security reports: https://github.com/arunvenkatadri/connectpak. MIT licensed.
