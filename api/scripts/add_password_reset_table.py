#!/usr/bin/env python3
"""
Migration script to add password reset token table
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the parent directory to Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models.database import engine
from core.models.models import Base, PasswordResetToken

def create_password_reset_table():
    """Create the password reset token table in the master database"""
    print("Creating password reset token table...")
    
    try:
        # Use the master database engine
        
        # Create the table
        PasswordResetToken.__table__.create(engine, checkfirst=True)
        
        print("✅ Password reset token table created successfully!")
        
        # Verify the table was created
        with engine.connect() as conn:
            # Check if we're using PostgreSQL or SQLite
            if engine.dialect.name == 'postgresql':
                result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name='password_reset_tokens';"))
                tables = result.fetchall()
                
                if tables:
                    print("✅ Table 'password_reset_tokens' verified in database")
                    
                    # Show table structure for PostgreSQL
                    result = conn.execute(text("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns 
                        WHERE table_schema='public' AND table_name='password_reset_tokens'
                        ORDER BY ordinal_position;
                    """))
                    columns = result.fetchall()
                    
                    print("\nTable structure:")
                    for col in columns:
                        print(f"  - {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'}")
                else:
                    print("❌ Table 'password_reset_tokens' not found in database")
            else:
                # SQLite
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='password_reset_tokens';"))
                tables = result.fetchall()
                
                if tables:
                    print("✅ Table 'password_reset_tokens' verified in database")
                    
                    # Show table structure for SQLite
                    result = conn.execute(text("PRAGMA table_info(password_reset_tokens);"))
                    columns = result.fetchall()
                    
                    print("\nTable structure:")
                    for col in columns:
                        print(f"  - {col[1]} ({col[2]})")
                else:
                    print("❌ Table 'password_reset_tokens' not found in database")
                
    except Exception as e:
        print(f"❌ Error creating password reset token table: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("Password Reset Token Table Migration")
    print("=" * 50)
    create_password_reset_table()
    print("=" * 50)
    print("Migration completed!") 