#!/usr/bin/env python3
"""Apply pending Alembic migrations to every tenant database.

Usage (from inside the api container):
    python scripts/migrate_all_tenants.py

Or for a specific revision:
    python scripts/migrate_all_tenants.py --revision 018_add_soft_delete_txn
"""
import os
import sys
import argparse
import subprocess
from urllib.parse import urlparse, urlunparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@db:5432/invoice_master")


def get_tenant_ids(master_url: str) -> list[int]:
    engine = create_engine(master_url)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id FROM tenants ORDER BY id")).fetchall()
    engine.dispose()
    return [r[0] for r in rows]


def tenant_db_url(master_url: str, tenant_id: int) -> str:
    parsed = urlparse(master_url)
    return urlunparse(parsed._replace(path=f"/tenant_{tenant_id}"))


def migrate_tenant(tenant_id: int, revision: str) -> bool:
    env = {**os.environ, "ALEMBIC_DB_TYPE": "tenant", "TENANT_ID": str(tenant_id)}
    result = subprocess.run(
        ["alembic", "upgrade", revision],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        return False
    print(f"  OK: {result.stdout.strip() or 'no output'}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate all tenant databases")
    parser.add_argument("--revision", default="head", help="Alembic revision target (default: head)")
    args = parser.parse_args()

    print(f"Fetching tenant IDs from master DB: {DATABASE_URL}")
    tenant_ids = get_tenant_ids(DATABASE_URL)
    print(f"Found {len(tenant_ids)} tenant(s): {tenant_ids}\n")

    success, failed = [], []
    for tid in tenant_ids:
        print(f"Migrating tenant {tid} → {args.revision} ...")
        if migrate_tenant(tid, args.revision):
            success.append(tid)
        else:
            failed.append(tid)

    print(f"\nDone. Success: {success}  Failed: {failed}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
