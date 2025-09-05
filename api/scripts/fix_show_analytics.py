#!/usr/bin/env python3
import os
from sqlalchemy import create_engine, text, inspect

def fix_show_analytics_column():
    database_url = os.getenv("DATABASE_URL")
    engine = create_engine(database_url)
    
    try:
        with engine.begin() as conn:
            inspector = inspect(conn)
            columns = [col['name'] for col in inspector.get_columns('master_users')]
            
            if 'show_analytics' not in columns:
                print("Adding show_analytics column...")
                conn.execute(text("""
                    ALTER TABLE master_users 
                    ADD COLUMN show_analytics BOOLEAN DEFAULT FALSE
                """))
                print("✅ Added show_analytics column")
            else:
                print("✅ show_analytics column already exists")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        engine.dispose()
    
    return True

if __name__ == "__main__":
    fix_show_analytics_column()