"""CLI entry point for the pgvector connector."""

from __future__ import annotations

import argparse
import os
import sys

from connectpak.core.server import serve
from connectpak.vector.pgvector.connector import PgvectorConnector


def main() -> int:
    parser = argparse.ArgumentParser(prog="connectpak-vector-pgvector")
    parser.add_argument(
        "--dsn",
        default=os.environ.get("CONNECTPAK_PGVECTOR_DSN")
        or os.environ.get("CONNECTPAK_POSTGRES_DSN"),
        help="Postgres DSN (default: $CONNECTPAK_PGVECTOR_DSN or $CONNECTPAK_POSTGRES_DSN).",
    )
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--statement-timeout-ms", type=int, default=30_000)
    parser.add_argument("--max-rows", type=int, default=1000)
    args = parser.parse_args()

    if not args.dsn:
        print(
            "error: --dsn is required "
            "(or set $CONNECTPAK_PGVECTOR_DSN / $CONNECTPAK_POSTGRES_DSN)",
            file=sys.stderr,
        )
        return 2

    connector = PgvectorConnector(
        dsn=args.dsn,
        allow_write=args.allow_write,
        statement_timeout_ms=args.statement_timeout_ms,
        default_max_rows=args.max_rows,
    )
    serve(connector)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
