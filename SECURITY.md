# Security Policy

## The safety model

connectpak is read-only by default and enforces that in two independent
layers, both of which must stay intact:

1. **Query guard** (`connectpak.core.guard`)
   - `assert_read_only` parses SQL with sqlglot and walks the full AST. It
     rejects any mutating statement, including ones hidden inside an allowed
     shape: CTE-wrapped writes (`WITH x AS (DELETE ...) SELECT ...`),
     `SELECT ... INTO`, row-locking reads (`FOR UPDATE` / `FOR SHARE`), and
     mutating `PRAGMA` setters.
   - `assert_no_write_keywords` screens the graph and wide-column query
     languages (Cypher, CQL, AQL, Gremlin) for write keywords. This is a
     coarser check than the SQL AST walk — it fails closed (a write keyword
     inside a string literal is rejected, not allowed).
   - Document/vector stores accept a JSON spec whose operation is
     whitelisted; MongoDB additionally rejects server-side-JavaScript
     operators (`$where`, `$function`, `$accumulator`) and the write
     aggregation stages (`$out`, `$merge`).

2. **Engine-level read-only** — each connector also asks the engine itself
   to refuse writes (Postgres `default_transaction_read_only`, MySQL
   `SET SESSION TRANSACTION READ ONLY`, ClickHouse `readonly=1`, SQLite
   `mode=ro` URI, Oracle `SET TRANSACTION READ ONLY`, Neo4j `execute_read`,
   etc.). Where an engine has no session read-only mode (SQL Server,
   BigQuery), point the connector at a read-only role.

Plus a statement timeout and a row cap on every query.

Identifiers passed to `sample_table` / `describe_table` are quoted with
engine-appropriate escaping (or parameterized, for Postgres). BigQuery
rejects identifiers containing a backtick since it cannot escape one.

### Defense in depth is your job too

The guard reduces risk; it does not replace least privilege. **Always point
the DSN at a database role that only has read permission.** Treat
`--allow-write` as a loaded gun.

## Reporting a vulnerability

Please report suspected vulnerabilities privately via GitHub's
[security advisory](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
flow on this repository, rather than opening a public issue.

Include: the connector/engine, a minimal reproduction (query or spec), and
what you expected versus what happened. We aim to acknowledge within a few
business days.

A guard bypass — any query that mutates state while `allow_write` is false —
is treated as high severity.
