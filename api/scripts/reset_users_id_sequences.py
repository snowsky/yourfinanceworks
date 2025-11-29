#!/usr/bin/env python3
"""
Reset users.id sequence for all tenant databases to avoid duplicate key errors.

When to use:
- Use this script/function if you have imported data, restored from backup, or performed manual operations that may have desynchronized the users.id sequence from the actual max(id) in the users table.
- It is NOT needed for fresh environments where the schema is created from scratch using SQLAlchemy's create_all() or Alembic migrations, as the sequence will be correct by default.
- For normal operation and seeding, always let the database assign IDs (do not set id manually).

Safe to run multiple times; it will always set the sequence to MAX(id)+1 for each tenant DB.
"""
from core.services.tenant_database_manager import TenantDatabaseManager
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_users_id_sequence_for_tenant(tenant_db_url):
    engine = create_engine(tenant_db_url)
    with engine.connect() as conn:
        # Get max id from users table
        result = conn.execute(text("SELECT MAX(id) FROM users"))
        max_id = result.scalar() or 0
        # Try to reset the sequence (assume default name users_id_seq)
        try:
            conn.execute(text(f"ALTER SEQUENCE users_id_seq RESTART WITH {max_id + 1};"))
            logger.info(f"users_id_seq in {tenant_db_url} reset to {max_id + 1}")
        except Exception as e:
            logger.error(f"Failed to reset sequence in {tenant_db_url}: {e}")

def reset_all_users_id_sequences():
    manager = TenantDatabaseManager()
    tenant_dbs = manager.get_all_tenant_databases()
    logger.info(f"Found {len(tenant_dbs)} tenant databases.")
    for db_name in tenant_dbs:
        try:
            tenant_id = int(db_name.replace("tenant_", ""))
            tenant_db_url = manager.get_tenant_database_url(tenant_id)
            reset_users_id_sequence_for_tenant(tenant_db_url)
        except Exception as e:
            logger.error(f"Error processing {db_name}: {e}")

# CLI entrypoint
if __name__ == "__main__":
    reset_all_users_id_sequences() 