#!/usr/bin/env python3
"""
Script to test approval workflow migration rollback scenarios

This script tests the rollback functionality of the approval workflow migrations
to ensure they can be safely reverted if needed.
"""

import os
import sys
import tempfile
import sqlite3
from pathlib import Path

# Add the API directory to the Python path
api_dir = Path(__file__).parent.parent
sys.path.insert(0, str(api_dir))

from sqlalchemy import create_engine, text, inspect
from alembic import command
from alembic.config import Config


def create_test_database():
    """Create a temporary test database"""
    temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_file.close()
    return temp_file.name


def setup_alembic_config(db_path):
    """Setup Alembic configuration for testing"""
    config = Config()
    config.set_main_option("script_location", str(api_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def test_migration_rollback():
    """Test the complete migration and rollback process"""
    print("🧪 Testing Approval Workflow Migration Rollback Scenarios")
    print("=" * 60)
    
    # Create test database
    db_path = create_test_database()
    print(f"📁 Created test database: {db_path}")
    
    try:
        # Setup Alembic
        config = setup_alembic_config(db_path)
        engine = create_engine(f"sqlite:///{db_path}")
        
        # Create base tables that the migrations depend on
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    expense_date DATETIME NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT DEFAULT 'recorded',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            conn.commit()
        
        print("\n1️⃣ Testing Forward Migration...")
        
        # Test forward migration to approval workflow tables
        print("   ⬆️  Upgrading to add_expense_approval_workflow_tables...")
        try:
            command.upgrade(config, "add_expense_approval_workflow_tables")
            print("   ✅ Approval workflow tables created successfully")
        except Exception as e:
            print(f"   ❌ Failed to create approval workflow tables: {e}")
            return False
        
        # Verify tables exist
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        expected_tables = ["expense_approvals", "approval_rules", "approval_delegates"]
        
        for table in expected_tables:
            if table in tables:
                print(f"   ✅ Table '{table}' exists")
            else:
                print(f"   ❌ Table '{table}' missing")
                return False
        
        # Test upgrade to status values migration
        print("   ⬆️  Upgrading to add_expense_approval_status_values...")
        try:
            command.upgrade(config, "add_expense_approval_status_values")
            print("   ✅ Expense status values updated successfully")
        except Exception as e:
            print(f"   ❌ Failed to update expense status values: {e}")
            return False
        
        # Test upgrade to indexes migration
        print("   ⬆️  Upgrading to update_approval_workflow_indexes...")
        try:
            command.upgrade(config, "update_approval_workflow_indexes")
            print("   ✅ Approval workflow indexes created successfully")
        except Exception as e:
            print(f"   ❌ Failed to create approval workflow indexes: {e}")
            return False
        
        print("\n2️⃣ Testing Rollback Scenarios...")
        
        # Test rollback from indexes migration
        print("   ⬇️  Rolling back from update_approval_workflow_indexes...")
        try:
            command.downgrade(config, "add_expense_approval_status_values")
            print("   ✅ Successfully rolled back indexes migration")
        except Exception as e:
            print(f"   ❌ Failed to rollback indexes migration: {e}")
            return False
        
        # Verify tables still exist but indexes are removed
        inspector = inspect(engine)
        tables_after_rollback = inspector.get_table_names()
        for table in expected_tables:
            if table in tables_after_rollback:
                print(f"   ✅ Table '{table}' still exists after indexes rollback")
            else:
                print(f"   ❌ Table '{table}' missing after indexes rollback")
                return False
        
        # Test rollback from status values migration
        print("   ⬇️  Rolling back from add_expense_approval_status_values...")
        try:
            command.downgrade(config, "add_expense_approval_workflow_tables")
            print("   ✅ Successfully rolled back status values migration")
        except Exception as e:
            print(f"   ❌ Failed to rollback status values migration: {e}")
            return False
        
        # Test rollback from workflow tables migration
        print("   ⬇️  Rolling back from add_expense_approval_workflow_tables...")
        try:
            command.downgrade(config, "base")
            print("   ✅ Successfully rolled back workflow tables migration")
        except Exception as e:
            print(f"   ❌ Failed to rollback workflow tables migration: {e}")
            return False
        
        # Verify tables are removed
        inspector = inspect(engine)
        tables_final = inspector.get_table_names()
        for table in expected_tables:
            if table not in tables_final:
                print(f"   ✅ Table '{table}' properly removed")
            else:
                print(f"   ❌ Table '{table}' still exists after full rollback")
                return False
        
        print("\n3️⃣ Testing Re-migration After Rollback...")
        
        # Test that we can re-apply migrations after rollback
        print("   ⬆️  Re-applying all migrations...")
        try:
            command.upgrade(config, "update_approval_workflow_indexes")
            print("   ✅ Successfully re-applied all migrations")
        except Exception as e:
            print(f"   ❌ Failed to re-apply migrations: {e}")
            return False
        
        # Final verification
        inspector = inspect(engine)
        tables_final = inspector.get_table_names()
        for table in expected_tables:
            if table in tables_final:
                print(f"   ✅ Table '{table}' exists after re-migration")
            else:
                print(f"   ❌ Table '{table}' missing after re-migration")
                return False
        
        print("\n🎉 All migration rollback tests passed!")
        return True
        
    except Exception as e:
        print(f"\n💥 Unexpected error during testing: {e}")
        return False
        
    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
            print(f"\n🧹 Cleaned up test database: {db_path}")


def test_constraint_validation():
    """Test that database constraints work correctly"""
    print("\n4️⃣ Testing Database Constraints...")
    
    db_path = create_test_database()
    
    try:
        config = setup_alembic_config(db_path)
        engine = create_engine(f"sqlite:///{db_path}")
        
        # Create base tables first
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    expense_date DATETIME NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT DEFAULT 'recorded',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            conn.commit()
        
        # Apply all migrations
        command.upgrade(config, "update_approval_workflow_indexes")
        
        with engine.connect() as conn:
            # Create base tables first
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY,
                    amount REAL NOT NULL,
                    currency TEXT DEFAULT 'USD',
                    expense_date DATETIME NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT DEFAULT 'recorded',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            conn.execute(text("""
                INSERT INTO users (email, hashed_password, role)
                VALUES ('test@example.com', 'hashed', 'admin')
            """))
            
            conn.execute(text("""
                INSERT INTO expenses (amount, currency, expense_date, category, status)
                VALUES (100.0, 'USD', '2025-01-01', 'travel', 'recorded')
            """))
            
            conn.commit()
            
            # Test valid approval status
            try:
                conn.execute(text("""
                    INSERT INTO expense_approvals 
                    (expense_id, approver_id, status, submitted_at, approval_level, is_current_level, created_at, updated_at)
                    VALUES (1, 1, 'pending', '2025-01-01 10:00:00', 1, 1, '2025-01-01 10:00:00', '2025-01-01 10:00:00')
                """))
                conn.commit()
                print("   ✅ Valid approval status accepted")
            except Exception as e:
                print(f"   ❌ Valid approval status rejected: {e}")
                return False
            
            # Test valid approval rule
            try:
                conn.execute(text("""
                    INSERT INTO approval_rules 
                    (name, approver_id, priority, approval_level, min_amount, max_amount, is_active, currency, created_at, updated_at)
                    VALUES ('Test Rule', 1, 1, 1, 50.0, 500.0, 1, 'USD', '2025-01-01 10:00:00', '2025-01-01 10:00:00')
                """))
                conn.commit()
                print("   ✅ Valid approval rule accepted")
            except Exception as e:
                print(f"   ❌ Valid approval rule rejected: {e}")
                return False
            
            # Test valid delegation
            try:
                conn.execute(text("""
                    INSERT INTO users (email, hashed_password, role)
                    VALUES ('delegate@example.com', 'hashed', 'user')
                """))
                
                conn.execute(text("""
                    INSERT INTO approval_delegates 
                    (approver_id, delegate_id, start_date, end_date, is_active, created_at, updated_at)
                    VALUES (1, 2, '2025-01-01', '2025-01-31', 1, '2025-01-01 10:00:00', '2025-01-01 10:00:00')
                """))
                conn.commit()
                print("   ✅ Valid delegation accepted")
            except Exception as e:
                print(f"   ❌ Valid delegation rejected: {e}")
                return False
        
        print("   🎉 All constraint validation tests passed!")
        return True
        
    except Exception as e:
        print(f"   💥 Constraint validation failed: {e}")
        return False
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


if __name__ == "__main__":
    success = True
    
    # Run migration rollback tests
    if not test_migration_rollback():
        success = False
    
    # Run constraint validation tests
    if not test_constraint_validation():
        success = False
    
    if success:
        print("\n🏆 All tests completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)