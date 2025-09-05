#!/usr/bin/env python3
"""
Fix missing must_reset_password column in master_users table
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect

def fix_must_reset_password_column():
    """Add the must_reset_password column to master_users table if it doesn't exist"""
    
    # Get the master database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not found")
        return False
    
    # Create engine
    engine = create_engine(database_url)
    
    try:
        with engine.begin() as conn:
            # Check if the column exists
            inspector = inspect(conn)
            columns = [col['name'] for col in inspector.get_columns('master_users')]
            
            if 'must_reset_password' not in columns:
                print("Adding must_reset_password column to master_users table...")
                
                # Add the column with default value
                conn.execute(text("""
                    ALTER TABLE master_users 
                    ADD COLUMN must_reset_password BOOLEAN NOT NULL DEFAULT FALSE
                """))
                
                print("✅ Successfully added must_reset_password column")
            else:
                print("✅ must_reset_password column already exists")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        engine.dispose()
    
    return True

if __name__ == "__main__":
    print("Fixing must_reset_password column in master_users table...")
    success = fix_must_reset_password_column()
    if success:
        print("✅ Fix completed successfully")
    else:
        print("❌ Fix failed")
        sys.exit(1)