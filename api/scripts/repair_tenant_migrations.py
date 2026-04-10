import os
import sys
from sqlalchemy import text, inspect
from core.services.tenant_database_manager import tenant_db_manager

def repair_tenant(tenant_id: int):
    print(f"Repairing migration tracking for tenant {tenant_id}...")
    
    # Get session for the tenant
    session_factory = tenant_db_manager.get_tenant_session(tenant_id)
    if not session_factory:
        print(f"Error: Could not get session for tenant {tenant_id}")
        return

    session = session_factory()
    try:
        # 1. Ensure alembic_version table exists
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) PRIMARY KEY
            )
        """))
        
        # 2. Check for missing columns in bank_statements
        inspector = inspect(session.bind)
        columns = [c['name'] for c in inspector.get_columns('bank_statements')]
        
        if 'bank_name' not in columns:
            print("Adding 'bank_name' column to 'bank_statements'...")
            session.execute(text("ALTER TABLE bank_statements ADD COLUMN bank_name VARCHAR(255) NULL"))
        else:
            print("'bank_name' column already exists.")

        # 3. Check for plugin_users table (added in 015)
        tables = inspector.get_table_names()
        if 'plugin_users' not in tables:
            print("Creating 'plugin_users' table (simulating migration 015)...")
            session.execute(text("""
                CREATE TABLE plugin_users (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL,
                    plugin_id VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    hashed_password VARCHAR(255) NULL,
                    first_name VARCHAR(255) NULL,
                    last_name VARCHAR(255) NULL,
                    google_id VARCHAR(255) NULL,
                    azure_ad_id VARCHAR(255) NULL,
                    stripe_customer_id VARCHAR(255) NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))
            session.execute(text("CREATE INDEX ix_plugin_users_email ON plugin_users (email)"))
        else:
            # Check for usage_count (added in 016)
            pu_columns = [c['name'] for c in inspector.get_columns('plugin_users')]
            if 'usage_count' not in pu_columns:
                print("Adding 'usage_count' column to 'plugin_users' (simulating migration 016)...")
                session.execute(text("ALTER TABLE plugin_users ADD COLUMN usage_count INTEGER DEFAULT 0 NOT NULL"))

        # 4. Stamp the version
        # Check current version
        result = session.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        target_version = '017_add_bank_name'
        
        if not result:
            print(f"Stamping database with version {target_version}...")
            session.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{target_version}')"))
        else:
            print(f"Current version is {result[0]}. Updating to {target_version}...")
            session.execute(text(f"UPDATE alembic_version SET version_num = '{target_version}'"))
            
        session.commit()
        print(f"Successfully repaired tenant {tenant_id}.")
        
    except Exception as e:
        session.rollback()
        print(f"Error repairing tenant {tenant_id}: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python repair_tenant_migrations.py <tenant_id>")
        sys.exit(1)
        
    try:
        t_id = int(sys.argv[1])
        repair_tenant(t_id)
    except ValueError:
        print("Error: Tenant ID must be an integer")
