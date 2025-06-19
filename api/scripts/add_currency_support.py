#!/usr/bin/env python3
"""
Database migration script to add multi-currency support
"""
import sqlite3
import os
from datetime import datetime

def migrate_currency_support():
    """Add currency support to the database"""
    
    # Database file path
    db_path = "invoice_app.db"
    
    if not os.path.exists(db_path):
        print("Database file not found. Please run the main migration script first.")
        return False
    
    print("Adding multi-currency support to database...")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Add default_currency to tenants table
        cursor.execute("PRAGMA table_info(tenants)")
        tenant_columns = [column[1] for column in cursor.fetchall()]
        
        if 'default_currency' not in tenant_columns:
            print("Adding default_currency column to tenants table...")
            cursor.execute("ALTER TABLE tenants ADD COLUMN default_currency VARCHAR DEFAULT 'USD'")
            cursor.execute("UPDATE tenants SET default_currency = 'USD' WHERE default_currency IS NULL")
        
        # Add preferred_currency to clients table  
        cursor.execute("PRAGMA table_info(clients)")
        client_columns = [column[1] for column in cursor.fetchall()]
        
        if 'preferred_currency' not in client_columns:
            print("Adding preferred_currency column to clients table...")
            cursor.execute("ALTER TABLE clients ADD COLUMN preferred_currency VARCHAR")
        
        # Add currency to invoices table
        cursor.execute("PRAGMA table_info(invoices)")
        invoice_columns = [column[1] for column in cursor.fetchall()]
        
        if 'currency' not in invoice_columns:
            print("Adding currency column to invoices table...")
            cursor.execute("ALTER TABLE invoices ADD COLUMN currency VARCHAR DEFAULT 'USD'")
            cursor.execute("UPDATE invoices SET currency = 'USD' WHERE currency IS NULL")
        
        # Add currency to payments table
        cursor.execute("PRAGMA table_info(payments)")
        payment_columns = [column[1] for column in cursor.fetchall()]
        
        if 'currency' not in payment_columns:
            print("Adding currency column to payments table...")
            cursor.execute("ALTER TABLE payments ADD COLUMN currency VARCHAR DEFAULT 'USD'")
            cursor.execute("UPDATE payments SET currency = 'USD' WHERE currency IS NULL")
        
        # Create currency_rates table for exchange rates
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='currency_rates'")
        if not cursor.fetchone():
            print("Creating currency_rates table...")
            cursor.execute("""
                CREATE TABLE currency_rates (
                    id INTEGER PRIMARY KEY,
                    tenant_id INTEGER NOT NULL,
                    from_currency VARCHAR NOT NULL,
                    to_currency VARCHAR NOT NULL,
                    rate FLOAT NOT NULL,
                    effective_date TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tenant_id) REFERENCES tenants (id),
                    UNIQUE(tenant_id, from_currency, to_currency, effective_date)
                )
            """)
            
            # Add some default exchange rates (these should be updated regularly in production)
            default_rates = [
                ('USD', 'EUR', 0.85),
                ('USD', 'GBP', 0.73),
                ('USD', 'CAD', 1.25),
                ('USD', 'AUD', 1.35),
                ('USD', 'JPY', 110.0),
                ('EUR', 'USD', 1.18),
                ('GBP', 'USD', 1.37),
                ('CAD', 'USD', 0.80),
                ('AUD', 'USD', 0.74),
                ('JPY', 'USD', 0.009)
            ]
            
            # Get all tenants to add default rates
            cursor.execute("SELECT id FROM tenants")
            tenants = cursor.fetchall()
            
            for tenant_id, in tenants:
                for from_curr, to_curr, rate in default_rates:
                    cursor.execute("""
                        INSERT INTO currency_rates (tenant_id, from_currency, to_currency, rate, effective_date)
                        VALUES (?, ?, ?, ?, datetime('now'))
                    """, (tenant_id, from_curr, to_curr, rate))
            
            print("Added default exchange rates")
        
        # Create supported_currencies table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='supported_currencies'")
        if not cursor.fetchone():
            print("Creating supported_currencies table...")
            cursor.execute("""
                CREATE TABLE supported_currencies (
                    id INTEGER PRIMARY KEY,
                    code VARCHAR UNIQUE NOT NULL,
                    name VARCHAR NOT NULL,
                    symbol VARCHAR NOT NULL,
                    decimal_places INTEGER DEFAULT 2,
                    is_active BOOLEAN DEFAULT 1 NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add common currencies
            currencies = [
                ('USD', 'US Dollar', '$', 2),
                ('EUR', 'Euro', '€', 2),
                ('GBP', 'British Pound', '£', 2),
                ('CAD', 'Canadian Dollar', 'C$', 2),
                ('AUD', 'Australian Dollar', 'A$', 2),
                ('JPY', 'Japanese Yen', '¥', 0),
                ('CHF', 'Swiss Franc', 'CHF', 2),
                ('CNY', 'Chinese Yuan', '¥', 2),
                ('INR', 'Indian Rupee', '₹', 2),
                ('BRL', 'Brazilian Real', 'R$', 2)
            ]
            
            for code, name, symbol, decimal_places in currencies:
                cursor.execute("""
                    INSERT INTO supported_currencies (code, name, symbol, decimal_places)
                    VALUES (?, ?, ?, ?)
                """, (code, name, symbol, decimal_places))
            
            print("Added supported currencies")
        
        # Commit changes
        conn.commit()
        print("Multi-currency support migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during currency migration: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_currency_support() 