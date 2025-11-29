#!/usr/bin/env python3
"""
Migration management script for multi-tenant invoice application.
Handles migrations for both master database and tenant databases.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# Add the parent directory to the path
sys.path.append(str(Path(__file__).parent.parent))

from core.models.database import SessionLocal
from core.models.models import Tenant
from core.services.tenant_database_manager import tenant_db_manager

def run_alembic_command(command, db_type='master', tenant_id=None):
    """Run an alembic command with the appropriate environment variables."""
    env = os.environ.copy()
    env['ALEMBIC_DB_TYPE'] = db_type
    
    if tenant_id:
        env['TENANT_ID'] = str(tenant_id)
    
    # Change to the API directory where alembic.ini is located
    api_dir = Path(__file__).parent.parent
    
    try:
        result = subprocess.run(
            ['python', '-m', 'alembic'] + command,
            cwd=api_dir,
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"Error running alembic command: {' '.join(command)}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False
        else:
            print(result.stdout)
            return True
    except Exception as e:
        print(f"Exception running alembic command: {e}")
        return False

def create_migration(message, db_type='master'):
    """Create a new migration."""
    print(f"Creating migration for {db_type} database: {message}")
    return run_alembic_command(['revision', '--autogenerate', '-m', message], db_type)

def upgrade_database(db_type='master', tenant_id=None, revision='head'):
    """Upgrade database to the specified revision."""
    if db_type == 'tenant' and tenant_id:
        print(f"Upgrading tenant {tenant_id} database to {revision}")
    else:
        print(f"Upgrading {db_type} database to {revision}")
    
    return run_alembic_command(['upgrade', revision], db_type, tenant_id)

def downgrade_database(db_type='master', tenant_id=None, revision='-1'):
    """Downgrade database to the specified revision."""
    if db_type == 'tenant' and tenant_id:
        print(f"Downgrading tenant {tenant_id} database to {revision}")
    else:
        print(f"Downgrading {db_type} database to {revision}")
    
    return run_alembic_command(['downgrade', revision], db_type, tenant_id)

def show_current_revision(db_type='master', tenant_id=None):
    """Show current database revision."""
    if db_type == 'tenant' and tenant_id:
        print(f"Current revision for tenant {tenant_id}:")
    else:
        print(f"Current revision for {db_type} database:")
    
    return run_alembic_command(['current'], db_type, tenant_id)

def show_migration_history(db_type='master', tenant_id=None):
    """Show migration history."""
    if db_type == 'tenant' and tenant_id:
        print(f"Migration history for tenant {tenant_id}:")
    else:
        print(f"Migration history for {db_type} database:")
    
    return run_alembic_command(['history'], db_type, tenant_id)

def upgrade_all_tenants(revision='head'):
    """Upgrade all tenant databases."""
    print("Upgrading all tenant databases...")
    
    # Get all tenants from master database
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        
        success_count = 0
        total_count = len(tenants)
        
        for tenant in tenants:
            print(f"\nUpgrading tenant {tenant.id} ({tenant.name})...")
            if upgrade_database('tenant', tenant.id, revision):
                success_count += 1
                print(f"✓ Successfully upgraded tenant {tenant.id}")
            else:
                print(f"✗ Failed to upgrade tenant {tenant.id}")
        
        print(f"\nUpgrade completed: {success_count}/{total_count} tenants upgraded successfully")
        return success_count == total_count
        
    finally:
        db.close()

def create_initial_migrations():
    """Create initial migrations for both master and tenant databases."""
    print("Creating initial migrations...")
    
    # Create master database migration
    print("\n1. Creating master database migration...")
    if not create_migration("Initial master database migration", "master"):
        return False
    
    # Create tenant database migration
    print("\n2. Creating tenant database migration...")
    if not create_migration("Initial tenant database migration", "tenant"):
        return False
    
    print("\n✓ Initial migrations created successfully!")
    return True

def setup_database_schema():
    """Set up database schema by running initial migrations."""
    print("Setting up database schema...")
    
    # Upgrade master database
    print("\n1. Upgrading master database...")
    if not upgrade_database("master"):
        return False
    
    # Upgrade all tenant databases
    print("\n2. Upgrading all tenant databases...")
    if not upgrade_all_tenants():
        return False
    
    print("\n✓ Database schema setup completed!")
    return True

def main():
    parser = argparse.ArgumentParser(description="Manage database migrations for multi-tenant invoice application")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create migration
    create_parser = subparsers.add_parser('create', help='Create a new migration')
    create_parser.add_argument('message', help='Migration message')
    create_parser.add_argument('--type', choices=['master', 'tenant'], default='master', help='Database type')
    
    # Upgrade
    upgrade_parser = subparsers.add_parser('upgrade', help='Upgrade database')
    upgrade_parser.add_argument('--type', choices=['master', 'tenant', 'all'], default='master', help='Database type')
    upgrade_parser.add_argument('--tenant-id', type=int, help='Tenant ID (required for tenant type)')
    upgrade_parser.add_argument('--revision', default='head', help='Target revision')
    
    # Downgrade
    downgrade_parser = subparsers.add_parser('downgrade', help='Downgrade database')
    downgrade_parser.add_argument('--type', choices=['master', 'tenant'], default='master', help='Database type')
    downgrade_parser.add_argument('--tenant-id', type=int, help='Tenant ID (required for tenant type)')
    downgrade_parser.add_argument('--revision', default='-1', help='Target revision')
    
    # Current
    current_parser = subparsers.add_parser('current', help='Show current revision')
    current_parser.add_argument('--type', choices=['master', 'tenant'], default='master', help='Database type')
    current_parser.add_argument('--tenant-id', type=int, help='Tenant ID (required for tenant type)')
    
    # History
    history_parser = subparsers.add_parser('history', help='Show migration history')
    history_parser.add_argument('--type', choices=['master', 'tenant'], default='master', help='Database type')
    history_parser.add_argument('--tenant-id', type=int, help='Tenant ID (required for tenant type)')
    
    # Initialize
    subparsers.add_parser('init', help='Create initial migrations')
    
    # Setup
    subparsers.add_parser('setup', help='Set up database schema')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'create':
            create_migration(args.message, args.type)
        
        elif args.command == 'upgrade':
            if args.type == 'all':
                upgrade_all_tenants(args.revision)
            elif args.type == 'tenant':
                if not args.tenant_id:
                    print("Error: --tenant-id is required for tenant upgrades")
                    return
                upgrade_database(args.type, args.tenant_id, args.revision)
            else:
                upgrade_database(args.type, None, args.revision)
        
        elif args.command == 'downgrade':
            if args.type == 'tenant' and not args.tenant_id:
                print("Error: --tenant-id is required for tenant downgrades")
                return
            downgrade_database(args.type, args.tenant_id, args.revision)
        
        elif args.command == 'current':
            if args.type == 'tenant' and not args.tenant_id:
                print("Error: --tenant-id is required for tenant current")
                return
            show_current_revision(args.type, args.tenant_id)
        
        elif args.command == 'history':
            if args.type == 'tenant' and not args.tenant_id:
                print("Error: --tenant-id is required for tenant history")
                return
            show_migration_history(args.type, args.tenant_id)
        
        elif args.command == 'init':
            create_initial_migrations()
        
        elif args.command == 'setup':
            setup_database_schema()
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()