#!/usr/bin/env python3
"""
Script to add custom currencies like Bitcoin and Ethereum to the database.
"""

import sqlite3
import os
from datetime import datetime, timezone

def add_custom_currencies():
    # Get the database path
    db_path = os.path.join(os.path.dirname(__file__), '..', 'invoice_app.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if supported_currencies table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='supported_currencies'")
        if not cursor.fetchone():
            print("supported_currencies table not found. Please run the currency support migration first.")
            return
        
        # Define custom currencies to add
        custom_currencies = [
            ('BTC', 'Bitcoin', '₿', 8),
            ('ETH', 'Ethereum', 'Ξ', 18),
            ('XRP', 'Ripple', 'XRP', 6),
            ('SOL', 'Solana', '◎', 9),
        ]
        
        # Check which currencies already exist
        existing_codes = set()
        cursor.execute("SELECT code FROM supported_currencies")
        for row in cursor.fetchall():
            existing_codes.add(row[0])
        
        # Add new currencies
        added_count = 0
        for code, name, symbol, decimals in custom_currencies:
            if code not in existing_codes:
                cursor.execute("""
                    INSERT INTO supported_currencies (code, name, symbol, decimal_places, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (code, name, symbol, decimals, True, datetime.now(timezone.utc)))
                print(f"Added {name} ({code}) with symbol {symbol}")
                added_count += 1
            else:
                print(f"Currency {code} already exists, skipping")
        
        conn.commit()
        print(f"\nSuccessfully added {added_count} new custom currencies!")
        
        # Show all currencies
        print("\nAll available currencies:")
        cursor.execute("SELECT code, name, symbol, decimal_places, is_active FROM supported_currencies ORDER BY code")
        for row in cursor.fetchall():
            code, name, symbol, decimals, is_active = row
            status = "Active" if is_active else "Inactive"
            print(f"  {code}: {name} ({symbol}) - {decimals} decimals - {status}")
        
    except Exception as e:
        print(f"Error adding custom currencies: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_custom_currencies() 