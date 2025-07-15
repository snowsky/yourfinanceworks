#!/usr/bin/env python3
"""
Comprehensive migration script to run all necessary database migrations.
This script ensures all databases are up to date with the latest schema.
"""

import sys
import os
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from models.database import get_master_db, DATABASE_URL
from models.models import Tenant
import logging
from scripts.reset_users_id_sequences import reset_all_users_id_sequences

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_master_database_migrations():
    """Run migrations on the master database"""
    try:
        logger.info("Running migrations on master database...")
        from scripts.init_ai_config_master import init_ai_config_master
        init_ai_config_master()
        logger.info("Master database migrations completed successfully")
    except Exception as e:
        logger.error(f"Error running master database migrations: {e}")
        raise

def run_tenant_database_migrations():
    """Ensure AI config table exists and is up to date in all tenant databases"""
    try:
        logger.info("Ensuring AI config table exists and is up to date in all tenant databases...")
        from scripts.init_ai_config_tenants import init_ai_config_tenants
        init_ai_config_tenants()
        logger.info("Tenant database migrations completed successfully")
    except Exception as e:
        logger.error(f"Error running tenant database migrations: {e}")
        raise

def run_all_migrations():
    """Run all migrations in the correct order"""
    try:
        logger.info("Starting comprehensive database migration...")
        run_master_database_migrations()
        run_tenant_database_migrations()
        logger.info("All migrations completed successfully!")
        # Reset users.id sequences for all tenant DBs
        reset_all_users_id_sequences()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    run_all_migrations() 