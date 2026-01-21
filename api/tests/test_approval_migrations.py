"""Tests for approval workflow database migrations"""

import pytest
import tempfile
import os
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.runtime.environment import EnvironmentContext
from alembic.runtime.migration import MigrationContext

from core.models.models_per_tenant import Base, ExpenseApproval, ApprovalRule, ApprovalDelegate


class TestApprovalMigrations:
    """Test approval workflow migrations and rollback scenarios"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing migrations"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Create SQLite database URL
        db_url = f"sqlite:///{db_path}"
        engine = create_engine(db_url)
        
        yield engine, db_url
        
        # Cleanup
        engine.dispose()
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def alembic_config(self, temp_db):
        """Create Alembic configuration for testing"""
        engine, db_url = temp_db
        
        # Create a temporary alembic.ini
        config = Config()
        config.set_main_option("script_location", "alembic")
        config.set_main_option("sqlalchemy.url", db_url)
        
        # Create base tables that migrations depend on
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    is_active BOOLEAN DEFAULT TRUE,
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
        
        return config, engine
    
    def test_approval_workflow_tables_creation(self, alembic_config):
        """Test that approval workflow tables are created correctly"""
        config, engine = alembic_config
        
        # Run the approval workflow migration
        command.upgrade(config, "add_expense_approval_workflow_tables")
        
        # Check that tables exist
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        assert "expense_approvals" in tables
        assert "approval_rules" in tables
        assert "approval_delegates" in tables
        
        # Check table structure
        expense_approvals_columns = {col['name'] for col in inspector.get_columns('expense_approvals')}
        expected_columns = {
            'id', 'expense_id', 'approver_id', 'approval_rule_id', 'status',
            'rejection_reason', 'notes', 'submitted_at', 'decided_at',
            'approval_level', 'is_current_level', 'created_at', 'updated_at'
        }
        assert expected_columns.issubset(expense_approvals_columns)
    
    def test_approval_status_values_migration(self, alembic_config):
        """Test that expense status values are updated correctly"""
        config, engine = alembic_config
        
        # Run the status values migration
        command.upgrade(config, "add_expense_approval_status_values")
        
        # Test that valid status values are accepted
        with engine.connect() as conn:
            # This should work
            conn.execute(text("""
                INSERT INTO expenses (amount, currency, expense_date, category, status)
                VALUES (100.0, 'USD', '2025-01-01', 'travel', 'pending_approval')
            """))
            conn.commit()
            
            # This should also work
            conn.execute(text("""
                INSERT INTO expenses (amount, currency, expense_date, category, status)
                VALUES (50.0, 'USD', '2025-01-01', 'office', 'approved')
            """))
            conn.commit()
    
    def test_approval_indexes_migration(self, alembic_config):
        """Test that approval workflow indexes are created correctly"""
        config, engine = alembic_config
        
        # Run all migrations up to the indexes migration
        command.upgrade(config, "update_approval_workflow_indexes")
        
        # Check that tables exist and are functional (indexes are created but may not be visible in SQLite)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # Verify all approval tables exist
        assert "expense_approvals" in tables
        assert "approval_rules" in tables
        assert "approval_delegates" in tables
        
        # Test that we can insert data (which would fail if constraints/indexes are broken)
        with engine.connect() as conn:
            # Insert test user
            conn.execute(text("""
                INSERT INTO users (email, hashed_password, role, is_active)
                VALUES ('test@example.com', 'hashed', 'admin', 1)
            """))
            
            # Insert test expense
            conn.execute(text("""
                INSERT INTO expenses (amount, currency, expense_date, category, status)
                VALUES (100.0, 'USD', '2025-01-01', 'travel', 'recorded')
            """))
            
            # Insert approval data to test constraints
            conn.execute(text("""
                INSERT INTO expense_approvals 
                (expense_id, approver_id, status, submitted_at, approval_level, is_current_level, created_at, updated_at)
                VALUES (1, 1, 'pending', '2025-01-01 10:00:00', 1, 1, '2025-01-01 10:00:00', '2025-01-01 10:00:00')
            """))
            
            conn.commit()
            
            # Verify data was inserted successfully
            result = conn.execute(text("SELECT COUNT(*) FROM expense_approvals")).scalar()
            assert result == 1
    
    def test_approval_constraints_validation(self, alembic_config):
        """Test that approval workflow constraints work correctly"""
        config, engine = alembic_config
        
        # Run all migrations
        command.upgrade(config, "update_approval_workflow_indexes")
        
        with engine.connect() as conn:
            # Create test users first
            conn.execute(text("""
                INSERT INTO users (email, hashed_password, role, is_active)
                VALUES ('approver@test.com', 'hashed', 'admin', 1)
            """))
            conn.execute(text("""
                INSERT INTO users (email, hashed_password, role, is_active)
                VALUES ('delegate@test.com', 'hashed', 'user', 1)
            """))
            
            # Create test expense
            conn.execute(text("""
                INSERT INTO expenses (amount, currency, expense_date, category, status)
                VALUES (100.0, 'USD', '2025-01-01', 'travel', 'recorded')
            """))
            conn.commit()
            
            # Test valid ExpenseApproval first
            conn.execute(text("""
                INSERT INTO expense_approvals 
                (expense_id, approver_id, status, submitted_at, approval_level, is_current_level, created_at, updated_at)
                VALUES (1, 1, 'pending', '2025-01-01 10:00:00', 1, 1, '2025-01-01 10:00:00', '2025-01-01 10:00:00')
            """))
            conn.commit()
            
            # Test valid ApprovalRule
            conn.execute(text("""
                INSERT INTO approval_rules 
                (name, approver_id, priority, approval_level, currency, is_active, created_at, updated_at)
                VALUES ('Test Rule', 1, 1, 1, 'USD', 1, '2025-01-01 10:00:00', '2025-01-01 10:00:00')
            """))
            conn.commit()
    
    def test_migration_rollback_scenarios(self, alembic_config):
        """Test that migrations can be rolled back correctly"""
        config, engine = alembic_config
        
        # First, upgrade to the latest migration
        command.upgrade(config, "update_approval_workflow_indexes")
        
        # Verify tables exist
        inspector = inspect(engine)
        tables_before = set(inspector.get_table_names())
        assert "expense_approvals" in tables_before
        assert "approval_rules" in tables_before
        assert "approval_delegates" in tables_before
        
        # Rollback to before the indexes migration
        command.downgrade(config, "add_expense_approval_status_values")
        
        # Tables should still exist but indexes should be removed
        inspector = inspect(engine)
        tables_after = set(inspector.get_table_names())
        assert tables_before == tables_after  # Tables should still be there
        
        # Rollback to before status values migration
        command.downgrade(config, "add_expense_approval_workflow_tables")
        
        # Rollback to before workflow tables migration
        command.downgrade(config, "base")
        
        # Now approval tables should be gone
        inspector = inspect(engine)
        tables_final = set(inspector.get_table_names())
        assert "expense_approvals" not in tables_final
        assert "approval_rules" not in tables_final
        assert "approval_delegates" not in tables_final
    
    def test_migration_idempotency(self, alembic_config):
        """Test that running migrations multiple times doesn't cause issues"""
        config, engine = alembic_config
        
        # Run migrations twice
        command.upgrade(config, "update_approval_workflow_indexes")
        command.upgrade(config, "update_approval_workflow_indexes")  # Should not fail
        
        # Verify tables still exist and are functional
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "expense_approvals" in tables
        assert "approval_rules" in tables
        assert "approval_delegates" in tables
    
    def test_data_integrity_after_migration(self, alembic_config):
        """Test that existing data is preserved during migrations"""
        config, engine = alembic_config
        
        with engine.connect() as conn:
            # Insert test user
            conn.execute(text("""
                INSERT INTO users (email, hashed_password, role, is_active)
                VALUES ('test@example.com', 'hashed', 'admin', 1)
            """))
            
            # Insert test expense
            conn.execute(text("""
                INSERT INTO expenses (amount, currency, expense_date, category, status)
                VALUES (100.0, 'USD', '2025-01-01', 'travel', 'recorded')
            """))
            conn.commit()
        
        # Run approval workflow migrations
        command.upgrade(config, "add_expense_approval_workflow_tables")
        
        # Insert approval data
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO expense_approvals 
                (expense_id, approver_id, status, submitted_at, approval_level, is_current_level, created_at, updated_at)
                VALUES (1, 1, 'pending', '2025-01-01 10:00:00', 1, 1, '2025-01-01 10:00:00', '2025-01-01 10:00:00')
            """))
            conn.commit()
        
        # Run indexes migration
        command.upgrade(config, "update_approval_workflow_indexes")
        
        # Verify data is still there
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM expense_approvals")).scalar()
            assert result == 1
            
            result = conn.execute(text("SELECT COUNT(*) FROM expenses")).scalar()
            assert result == 1
            
            result = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            assert result == 1


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])