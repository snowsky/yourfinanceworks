#!/usr/bin/env python3
"""
Script to run database migrations
"""
import os
import sys
from alembic.config import Config
from alembic import command

# Change to api directory
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Create alembic config
alembic_cfg = Config('alembic.ini')

# Run upgrade to head
try:
    print("Running migrations...")
    command.upgrade(alembic_cfg, 'head')
    print("✓ Migrations completed successfully")
except Exception as e:
    print(f"✗ Migration failed: {e}")
    sys.exit(1)
