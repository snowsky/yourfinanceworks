#!/usr/bin/env python3
"""
Verify that the must_reset_password column exists and is properly configured
"""

import os
from sqlalchemy import create_engine, inspect

def verify_must_reset_password_column():
    """Verify the must_reset_password column exists and has correct properties"""
    
    # Get the master database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not found")
        return False
    
    # Create engine
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as conn:
            # Check if the column exists and get its properties
            inspector = inspect(conn)
            columns = inspector.get_columns('master_users')
            
            must_reset_column = None
            for col in columns:
                if col['name'] == 'must_reset_password':
                    must_reset_column = col
                    break
            
            if must_reset_column:
                print("✅ must_reset_password column exists")
                print(f"   Type: {must_reset_column['type']}")
                print(f"   Nullable: {must_reset_column['nullable']}")
                print(f"   Default: {must_reset_column.get('default', 'None')}")
                return True
            else:
                print("❌ must_reset_password column does not exist")
                return False
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        engine.dispose()

if __name__ == "__main__":
    print("Verifying must_reset_password column in master_users table...")
    success = verify_must_reset_password_column()
    if success:
        print("✅ Verification completed successfully")
    else:
        print("❌ Verification failed")