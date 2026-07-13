#!/usr/bin/env python3
"""
FUDS Database Clear Script
--------------------------
Deletes ALL application data from the PostgreSQL database (all tables mapped
by SQLAlchemy models). Optionally flushes Redis (carts, OTP, token blacklist).

Schema / migrations are left intact — only row data is removed.
Primary-key sequences are restarted (PostgreSQL).

Usage:
    # Interactive confirm
    python scripts/clear_db.py

    # Skip confirm
    python scripts/clear_db.py --yes

    # Also wipe Redis
    python scripts/clear_db.py --yes --redis
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Project root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db.session import SessionLocal, engine
from api.utils.settings import settings
from api.v1.models import Base


def _table_names() -> list[str]:
    """Tables in FK-safe delete order (children first)."""
    return [t.name for t in reversed(Base.metadata.sorted_tables)]


def clear_postgres(db: Session) -> list[str]:
    """
    Truncate every SQLAlchemy-mapped table.
    Uses TRUNCATE ... RESTART IDENTITY CASCADE on PostgreSQL.
    Falls back to DELETE for other dialects.
    """
    tables = _table_names()
    if not tables:
        return []

    dialect = engine.dialect.name
    if dialect == "postgresql":
        # Quote identifiers; CASCADE handles any leftover FKs
        joined = ", ".join(f'"{name}"' for name in tables)
        db.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))
        db.commit()
    else:
        # Generic path: delete in reverse dependency order
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()

    return tables


def clear_redis() -> int:
    """FLUSHDB on the configured Redis DB. Returns number of keys before flush (approx)."""
    from api.utils.redis_utils import redis_client

    try:
        key_count = redis_client.dbsize()
    except Exception:
        key_count = -1
    redis_client.flushdb()
    return key_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete all FUDS application data (DB rows; optional Redis)."
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip interactive confirmation",
    )
    parser.add_argument(
        "--redis",
        action="store_true",
        help="Also FLUSHDB the Redis instance (carts, OTP, blacklists)",
    )
    args = parser.parse_args()

    # Mask password in URL for display
    db_url = settings.DATABASE_URL
    safe_url = db_url
    if "@" in db_url:
        # postgresql+psycopg2://user:pass@host/db → user:***@host/db
        try:
            prefix, rest = db_url.split("://", 1)
            creds, hostpart = rest.split("@", 1)
            user = creds.split(":")[0]
            safe_url = f"{prefix}://{user}:***@{hostpart}"
        except ValueError:
            pass

    tables = _table_names()
    print("⚠️  FUDS clear_db")
    print(f"   Database: {safe_url}")
    print(f"   Tables ({len(tables)}): {', '.join(tables)}")
    if args.redis:
        print(f"   Redis:    {settings.REDIS_URL} (FLUSHDB)")
    print()

    if not args.yes:
        confirm = input('Type "DELETE" to wipe all data: ').strip()
        if confirm != "DELETE":
            print("Aborted. No data was deleted.")
            return 1

    db = SessionLocal()
    try:
        cleared = clear_postgres(db)
        print(f"✅ Cleared {len(cleared)} table(s): {', '.join(cleared)}")
    except Exception as exc:
        db.rollback()
        print(f"❌ Database clear failed: {exc}")
        return 1
    finally:
        db.close()

    if args.redis:
        try:
            n = clear_redis()
            msg = f"~{n} keys" if n >= 0 else "all keys"
            print(f"✅ Redis FLUSHDB complete ({msg})")
        except Exception as exc:
            print(f"❌ Redis clear failed: {exc}")
            return 1

    print("\nDone. You can re-seed with: python scripts/seed_db.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
