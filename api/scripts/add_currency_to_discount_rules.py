#!/usr/bin/env python3
"""
Script to add the currency column to the discount_rules table.
"""

import sqlite3
import os

def add_currency_column():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'invoice_app.db')
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(discount_rules)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'currency' in columns:
            print("currency column already exists in discount_rules table.")
            return
        print("Adding currency column to discount_rules table...")
        cursor.execute("ALTER TABLE discount_rules ADD COLUMN currency VARCHAR DEFAULT 'USD' NOT NULL")
        conn.commit()
        print("Successfully added currency column to discount_rules table!")
    except Exception as e:
        print(f"Error adding currency column: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_currency_column() 