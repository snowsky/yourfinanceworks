#!/usr/bin/env python3
"""
Script to clean up currencies and keep only the desired ones.
"""

import sqlite3
import os
from datetime import datetime, timezone

def cleanup_currencies():
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
            print("supported_currencies table not found.")
            return
        
        # Define the currencies we want to keep
        desired_currencies = {
            # Traditional currencies
            'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY', 'CHF', 'CNY', 'INR', 'BRL',
            # Cryptocurrencies
            'BTC', 'ETH', 'XRP', 'SOL'
        }
        
        # Get all current currencies
        cursor.execute("SELECT code, name FROM supported_currencies")
        current_currencies = cursor.fetchall()
        
        print("Current currencies in database:")
        for code, name in current_currencies:
            print(f"  {code}: {name}")
        
        # Find currencies to remove
        currencies_to_remove = []
        for code, name in current_currencies:
            if code not in desired_currencies:
                currencies_to_remove.append((code, name))
        
        if not currencies_to_remove:
            print("\nNo unwanted currencies found. All currencies are already correct.")
            return
        
        print(f"\nCurrencies to remove ({len(currencies_to_remove)}):")
        for code, name in currencies_to_remove:
            print(f"  {code}: {name}")
        
        # Check if any of these currencies are being used
        for code, name in currencies_to_remove:
            # Check invoices
            cursor.execute("SELECT COUNT(*) FROM invoices WHERE currency = ?", (code,))
            invoice_count = cursor.fetchone()[0]
            
            # Check payments
            cursor.execute("SELECT COUNT(*) FROM payments WHERE currency = ?", (code,))
            payment_count = cursor.fetchone()[0]
            
            if invoice_count > 0 or payment_count > 0:
                print(f"⚠️  Cannot remove {code} ({name}) - used in {invoice_count} invoices and {payment_count} payments")
                # Deactivate instead of delete
                cursor.execute("""
                    UPDATE supported_currencies 
                    SET is_active = 0, updated_at = ? 
                    WHERE code = ?
                """, (datetime.now(timezone.utc), code))
                print(f"  → Deactivated {code} instead of deleting")
            else:
                # Safe to delete
                cursor.execute("DELETE FROM supported_currencies WHERE code = ?", (code,))
                print(f"  ✅ Deleted {code}")
        
        conn.commit()
        print(f"\nCleanup completed!")
        
        # Show final currency list
        print("\nFinal active currencies:")
        cursor.execute("SELECT code, name, symbol, decimal_places FROM supported_currencies WHERE is_active = 1 ORDER BY code")
        for row in cursor.fetchall():
            code, name, symbol, decimals = row
            print(f"  {code}: {name} ({symbol}) - {decimals} decimals")
        
    except Exception as e:
        print(f"Error cleaning up currencies: {e}")
        conn.rollback()
    finally:
        conn.close()

def main():
    cleanup_currencies()

if __name__ == "__main__":
    main() 