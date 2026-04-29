"""pgvector connector — Postgres + vector-aware describe_table.

Inherits the full Postgres implementation from connectpak-sql-postgres and
overrides `_fetch_columns` to report the real `vector(N)` type for vector
columns (information_schema.columns reports them as 'USER-DEFINED' which
hides the dimension).
"""

from __future__ import annotations

from connectpak.core.base import Column
from connectpak.sql.postgres.connector import PostgresConnector


class PgvectorConnector(PostgresConnector):
    name = "pgvector"

    def _fetch_columns(self, schema: str, table: str) -> list[Column]:
        sql = """
            SELECT
              a.attname,
              format_type(a.atttypid, a.atttypmod) AS data_type,
              NOT a.attnotnull AS nullable,
              pg_get_expr(d.adbin, d.adrelid) AS column_default,
              col_description(c.oid, a.attnum) AS comment
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
            WHERE n.nspname = %s AND c.relname = %s
              AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY a.attnum
        """
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            return [
                Column(
                    name=r[0],
                    type=r[1],
                    nullable=bool(r[2]),
                    default=r[3],
                    comment=r[4],
                )
                for r in cur.fetchall()
            ]
