"""CLI entry point for the SQLite connector."""

from __future__ import annotations

import argparse
import os
import sys

from connectpak.core.server import serve
from connectpak.sql.sqlite.connector import SqliteConnector


def main() -> int:
    parser = argparse.ArgumentParser(prog="connectpak-sql-sqlite")
    parser.add_argument(
        "--path",
        default=os.environ.get("CONNECTPAK_SQLITE_PATH"),
        help="Path to SQLite database (default: $CONNECTPAK_SQLITE_PATH).",
    )
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--statement-timeout-ms", type=int, default=30_000)
    parser.add_argument("--max-rows", type=int, default=1000)
    args = parser.parse_args()

    if not args.path:
        print(
            "error: --path is required (or set $CONNECTPAK_SQLITE_PATH)",
            file=sys.stderr,
        )
        return 2

    connector = SqliteConnector(
        path=args.path,
        allow_write=args.allow_write,
        statement_timeout_ms=args.statement_timeout_ms,
        default_max_rows=args.max_rows,
    )
    serve(connector)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
