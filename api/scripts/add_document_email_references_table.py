#!/usr/bin/env python3
"""
Migration: add document_email_references table to all tenant databases.

Run once:
    docker compose exec api python scripts/add_document_email_references_table.py

Phases:
  A - Create the junction table + indexes
  B - Backfill from legacy raw_emails.expense_id
"""

import sys
import os
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from core.models.database import DATABASE_URL
from core.models.models import Tenant

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


DDL = """
CREATE TABLE IF NOT EXISTS document_email_references (
    id                  SERIAL PRIMARY KEY,
    raw_email_id        INTEGER NOT NULL REFERENCES raw_emails(id) ON DELETE CASCADE,
    document_type       VARCHAR(50) NOT NULL,
    document_id         INTEGER NOT NULL,
    link_type           VARCHAR(20) NOT NULL DEFAULT 'auto',
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_user_id  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT uq_email_document UNIQUE (raw_email_id, document_type, document_id)
);
CREATE INDEX IF NOT EXISTS ix_der_raw_email_id
    ON document_email_references(raw_email_id);
CREATE INDEX IF NOT EXISTS ix_der_document
    ON document_email_references(document_type, document_id);
"""

BACKFILL = """
INSERT INTO document_email_references
    (raw_email_id, document_type, document_id, link_type, created_at)
SELECT
    id,
    'expense',
    expense_id,
    'auto',
    COALESCE(processed_at, created_at, NOW())
FROM raw_emails
WHERE expense_id IS NOT NULL
ON CONFLICT (raw_email_id, document_type, document_id) DO NOTHING;
"""


def migrate_tenant_db(tenant_db_url: str, tenant_id: int) -> bool:
    try:
        engine = create_engine(tenant_db_url)
        with engine.connect() as conn:
            # Phase A — DDL
            conn.execute(text(DDL))
            # Phase B — Backfill
            result = conn.execute(text(BACKFILL))
            conn.commit()
            logger.info(
                f"Tenant {tenant_id}: table created, {result.rowcount} existing links backfilled"
            )
        return True
    except Exception as exc:
        logger.error(f"Tenant {tenant_id}: migration failed — {exc}")
        return False


def _tenant_db_url(master_url: str, tenant_id: int) -> str:
    """Build tenant DB URL from master URL by replacing the DB name."""
    # e.g. postgresql://user:pass@host/invoice_master → postgresql://user:pass@host/tenant_42
    if "/" not in master_url:
        raise ValueError(f"Cannot derive tenant URL from: {master_url}")
    base = master_url.rsplit("/", 1)[0]
    return f"{base}/tenant_{tenant_id}"


def main():
    master_engine = create_engine(DATABASE_URL)
    with master_engine.connect() as conn:
        tenants = conn.execute(text("SELECT id FROM tenants WHERE is_active = true")).fetchall()

    logger.info(f"Migrating {len(tenants)} tenant(s)...")
    ok = 0
    for row in tenants:
        tenant_url = _tenant_db_url(DATABASE_URL, row.id)
        if migrate_tenant_db(tenant_url, row.id):
            ok += 1
    logger.info(f"Done: {ok}/{len(tenants)} tenant(s) migrated successfully.")
    if ok < len(tenants):
        sys.exit(1)


if __name__ == "__main__":
    main()
