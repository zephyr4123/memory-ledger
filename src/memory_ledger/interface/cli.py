"""memory-ledger CLI —— driving adapter (入口). 目前提供 init-db 引导建表.

用法:
    memory-ledger init-db "postgresql://user:pass@host/db"
    memory-ledger init-db "$DATABASE_URL" --core-only
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="memory-ledger")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init-db", help="apply bundled SQL schema to a Postgres DB")
    p_init.add_argument("dsn", help="Postgres DSN, e.g. postgresql://localhost/mydb")
    p_init.add_argument(
        "--core-only",
        action="store_true",
        help="只建核心账本表, 不建 todo 示例实体",
    )

    args = parser.parse_args(argv)

    if args.cmd == "init-db":
        return _init_db(args.dsn, core_only=args.core_only)
    return 1


def _init_db(dsn: str, *, core_only: bool) -> int:
    try:
        import psycopg
    except ImportError:
        print("需要 psycopg: pip install 'memory-ledger[psycopg]'", file=sys.stderr)
        return 2

    from ..infrastructure.persistence import (
        CORE_MIGRATION,
        DEFAULT_MIGRATIONS,
        PsycopgAdapter,
        apply_schema,
    )

    files = (CORE_MIGRATION,) if core_only else DEFAULT_MIGRATIONS
    with psycopg.connect(dsn, autocommit=True) as conn:
        apply_schema(PsycopgAdapter(conn), files)
    print(f"memory-ledger: applied {', '.join(files)} ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
