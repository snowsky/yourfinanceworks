"""
Database migration script to create API key and external transaction tables.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
import os
from core.models.models import Base
from core.models.api_models import APIClient, ExternalTransaction, ClientPermission

def create_api_key_tables():
    """Create API key related tables in the master database."""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        database_url = "sqlite:///./test.db"
    
    engine = create_engine(database_url)
    
    print("Creating API key tables...")
    
    # Create tables
    try:
        # Import all models to ensure they're registered with Base
        from core.models.api_models import APIClient, ExternalTransaction, ClientPermission
        
        # Create the tables
        Base.metadata.create_all(bind=engine, tables=[
            APIClient.__table__,
            ExternalTransaction.__table__,
            ClientPermission.__table__
        ])
        
        print("✅ API key tables created successfully!")
        
        # Add indexes for better performance
        with engine.connect() as conn:
            # Indexes for APIClient table
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_api_clients_user_tenant ON api_clients(user_id, tenant_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_api_clients_active ON api_clients(is_active)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_api_clients_created_at ON api_clients(created_at)"))
                print("✅ APIClient indexes created successfully!")
            except Exception as e:
                print(f"⚠️  Warning: Could not create APIClient indexes: {e}")
            
            # Indexes for ExternalTransaction table
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_external_transactions_user_tenant ON external_transactions(user_id, tenant_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_external_transactions_client ON external_transactions(external_client_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_external_transactions_date ON external_transactions(date)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_external_transactions_status ON external_transactions(status)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_external_transactions_type ON external_transactions(transaction_type)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_external_transactions_duplicate_hash ON external_transactions(duplicate_check_hash)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_external_transactions_created_at ON external_transactions(created_at)"))
                print("✅ ExternalTransaction indexes created successfully!")
            except Exception as e:
                print(f"⚠️  Warning: Could not create ExternalTransaction indexes: {e}")
            
            # Indexes for ClientPermission table
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_client_permissions_client ON client_permissions(client_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_client_permissions_active ON client_permissions(is_active)"))
                print("✅ ClientPermission indexes created successfully!")
            except Exception as e:
                print(f"⚠️  Warning: Could not create ClientPermission indexes: {e}")
            
            conn.commit()
        
        print("\n🎉 All API key tables and indexes created successfully!")
        print("\nNext steps:")
        print("1. Update main.py to include the new routes and middleware")
        print("2. Create the React UI components for API key management")
        print("3. Test the API key functionality")
        
    except Exception as e:
        print(f"❌ Error creating API key tables: {e}")
        raise

if __name__ == "__main__":
    create_api_key_tables()
