#!/usr/bin/env python3
"""
Script to add traditional currencies to the database.
"""

import sqlite3
import os
from datetime import datetime, timezone

def add_traditional_currencies():
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
        
        # Define traditional currencies to add
        traditional_currencies = [
            ('USD', 'US Dollar', '$', 2),
            ('EUR', 'Euro', '€', 2),
            ('GBP', 'British Pound', '£', 2),
            ('CAD', 'Canadian Dollar', 'C$', 2),
            ('AUD', 'Australian Dollar', 'A$', 2),
            ('JPY', 'Japanese Yen', '¥', 0),
            ('CHF', 'Swiss Franc', 'CHF', 2),
            ('CNY', 'Chinese Yuan', '¥', 2),
            ('INR', 'Indian Rupee', '₹', 2),
            ('BRL', 'Brazilian Real', 'R$', 2),
        ]
        
        # Check which currencies already exist
        existing_codes = set()
        cursor.execute("SELECT code FROM supported_currencies")
        for row in cursor.fetchall():
            existing_codes.add(row[0])
        
        # Add new currencies
        added_count = 0
        for code, name, symbol, decimals in traditional_currencies:
            if code not in existing_codes:
                cursor.execute("""
                    INSERT INTO supported_currencies (code, name, symbol, decimal_places, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (code, name, symbol, decimals, True, datetime.now(timezone.utc), datetime.now(timezone.utc)))
                print(f"Added {name} ({code}) with symbol {symbol}")
                added_count += 1
            else:
                # Update existing currency to ensure it's active
                cursor.execute("""
                    UPDATE supported_currencies 
                    SET is_active = 1, updated_at = ? 
                    WHERE code = ?
                """, (datetime.now(timezone.utc), code))
                print(f"Updated {name} ({code}) to be active")
        
        conn.commit()
        print(f"\nSuccessfully processed {len(traditional_currencies)} traditional currencies!")
        
        # Show all active currencies
        print("\nAll active currencies:")
        cursor.execute("SELECT code, name, symbol, decimal_places FROM supported_currencies WHERE is_active = 1 ORDER BY code")
        for row in cursor.fetchall():
            code, name, symbol, decimals = row
            print(f"  {code}: {name} ({symbol}) - {decimals} decimals")
        
    except Exception as e:
        print(f"Error adding traditional currencies: {e}")
        conn.rollback()
    finally:
        conn.close()

def main():
    add_traditional_currencies()

if __name__ == "__main__":
    main() 