#!/usr/bin/env python3
"""
Migration script to transfer data from SQLite to PostgreSQL
"""

import sqlite3
import psycopg2
import os
import sys
from datetime import datetime
import json

def connect_sqlite():
    """Connect to SQLite database"""
    try:
        conn = sqlite3.connect('invoice_app.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Error connecting to SQLite: {e}")
        sys.exit(1)

def connect_postgresql():
    """Connect to PostgreSQL database"""
    try:
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/invoice_app")
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        sys.exit(1)

def get_table_names(sqlite_conn):
    """Get all table names from SQLite"""
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row['name'] for row in cursor.fetchall()]
    cursor.close()
    return tables

def migrate_table(sqlite_conn, pg_conn, table_name):
    """Migrate a single table from SQLite to PostgreSQL"""
    print(f"Migrating table: {table_name}")
    
    # Get data from SQLite
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()
    
    if not rows:
        print(f"  No data in table {table_name}")
        return
    
    # Get column names
    columns = [description[0] for description in sqlite_cursor.description]
    
    # Create PostgreSQL cursor
    pg_cursor = pg_conn.cursor()
    
    # Prepare insert statement
    placeholders = ','.join(['%s'] * len(columns))
    insert_sql = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
    
    # Convert rows to tuples and handle data types
    converted_rows = []
    for row in rows:
        converted_row = []
        for value in row:
            if isinstance(value, datetime):
                converted_row.append(value.isoformat())
            elif isinstance(value, dict):
                converted_row.append(json.dumps(value))
            elif value is None:
                converted_row.append(None)
            else:
                converted_row.append(value)
        converted_rows.append(tuple(converted_row))
    
    try:
        # Insert data
        pg_cursor.executemany(insert_sql, converted_rows)
        pg_conn.commit()
        print(f"  Migrated {len(converted_rows)} rows")
    except Exception as e:
        print(f"  Error migrating {table_name}: {e}")
        pg_conn.rollback()
        raise
    
    pg_cursor.close()
    sqlite_cursor.close()

def reset_sequences(pg_conn):
    """Reset PostgreSQL sequences after migration"""
    print("Resetting sequences...")
    
    # Get all tables with serial columns
    cursor = pg_conn.cursor()
    cursor.execute("""
        SELECT table_name, column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND column_default LIKE 'nextval%'
    """)
    
    sequences = cursor.fetchall()
    
    for table_name, column_name in sequences:
        try:
            cursor.execute(f"SELECT setval(pg_get_serial_sequence('{table_name}', '{column_name}'), (SELECT MAX({column_name}) FROM {table_name}))")
            print(f"  Reset sequence for {table_name}.{column_name}")
        except Exception as e:
            print(f"  Error resetting sequence for {table_name}.{column_name}: {e}")
    
    pg_conn.commit()
    cursor.close()

def main():
    """Main migration function"""
    print("Starting migration from SQLite to PostgreSQL...")
    
    # Connect to databases
    sqlite_conn = connect_sqlite()
    pg_conn = connect_postgresql()
    
    try:
        # Get all tables
        tables = get_table_names(sqlite_conn)
        print(f"Found {len(tables)} tables: {', '.join(tables)}")
        
        # Migrate each table
        for table in tables:
            if table != 'sqlite_sequence':  # Skip SQLite internal table
                migrate_table(sqlite_conn, pg_conn, table)
        
        # Reset sequences
        reset_sequences(pg_conn)
        
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    main() 