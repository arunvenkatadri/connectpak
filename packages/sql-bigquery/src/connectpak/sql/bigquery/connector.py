"""BigQuery connector using google-cloud-bigquery.

Config:
    The GCP project ID. Authentication uses Application Default Credentials.

BigQuery has no session-level read-only mode, so write protection here is
the parser guard. For production deployments, use a service account with
only `bigquery.dataViewer` / `bigquery.jobUser` roles.

`list_schemas()` returns datasets in the project; `list_tables(schema=...)`
lists tables in that dataset; `describe_table(name, schema=...)` reports
columns and (where present) the partitioning / clustering as indexes.
BigQuery has no traditional foreign keys.
"""

from __future__ import annotations

import time
from typing import Any

from connectpak.core.base import (
    BaseConnector,
    Column,
    Index,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import assert_read_only
from google.cloud import bigquery


class BigQueryConnector(BaseConnector):
    name = "bigquery"
    dialect = "bigquery"

    def __init__(
        self,
        config: str,
        *,
        allow_write: bool = False,
        statement_timeout_ms: int = 30_000,
        default_max_rows: int = 1000,
    ):
        self.project = config
        self.allow_write = allow_write
        self.statement_timeout_ms = statement_timeout_ms
        self.default_max_rows = default_max_rows
        self._client: bigquery.Client | None = None

    def _connection(self) -> bigquery.Client:
        if self._client is not None:
            return self._client
        self._client = bigquery.Client(project=self.project)
        return self._client

    def list_schemas(self) -> list[str]:
        return sorted(ds.dataset_id for ds in self._connection().list_datasets())

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        client = self._connection()
        if schema is None:
            datasets = [ds.dataset_id for ds in client.list_datasets()]
        else:
            datasets = [schema]
        out: list[tuple[str | None, str]] = []
        for ds in datasets:
            for tbl in client.list_tables(ds):
                out.append((ds, tbl.table_id))
        return out

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        if schema is None:
            raise ValueError("BigQuery describe_table requires a dataset (schema)")
        client = self._connection()
        ref = client.dataset(schema).table(name)
        tbl = client.get_table(ref)

        cols = [
            Column(
                name=f.name,
                type=f.field_type + (f"({f.mode})" if f.mode != "NULLABLE" else ""),
                nullable=(f.mode != "REQUIRED"),
                comment=f.description,
            )
            for f in tbl.schema
        ]

        indexes: list[Index] = []
        if tbl.time_partitioning and tbl.time_partitioning.field:
            indexes.append(Index(
                name=f"_partition_{tbl.time_partitioning.field}",
                columns=[tbl.time_partitioning.field], unique=False,
            ))
        if tbl.clustering_fields:
            indexes.append(Index(
                name="_clustering", columns=list(tbl.clustering_fields), unique=False,
            ))

        return TableSchema(
            schema=schema, name=name, columns=cols, primary_key=[],
            foreign_keys=[], indexes=indexes, comment=tbl.description,
        )

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        if schema is None:
            raise ValueError("BigQuery sample_table requires a dataset (schema)")
        sql = f"SELECT * FROM `{self.project}.{schema}.{name}` LIMIT {int(limit)}"
        return self._run(sql, max_rows=limit)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        if not self.allow_write:
            assert_read_only(sql, dialect=self.dialect)
        return self._run(sql, max_rows=max_rows)

    def explain(self, sql: str) -> str:
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        job = self._connection().query(sql, job_config=job_config)
        return (
            f"dry_run: total_bytes_processed={job.total_bytes_processed}, "
            f"statement_type={job.statement_type}"
        )

    def _run(self, sql: str, max_rows: int | None = None) -> QueryResult:
        cap = max_rows if max_rows is not None else self.default_max_rows
        timeout_s = max(1.0, self.statement_timeout_ms / 1000.0)
        start = time.perf_counter()
        job = self._connection().query(sql)
        result = job.result(timeout=timeout_s, max_results=cap + 1)
        rows: list[list[Any]] = []
        cols = [f.name for f in result.schema]
        for r in result:
            if len(rows) >= cap + 1:
                break
            rows.append([r[c] for c in cols])
        elapsed = (time.perf_counter() - start) * 1000.0
        truncated = len(rows) > cap
        if truncated:
            rows = rows[:cap]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None
