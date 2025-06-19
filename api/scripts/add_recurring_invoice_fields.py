import sqlite3
import os

def add_recurring_invoice_fields():
    db_path = os.path.join(os.path.dirname(__name__), '..', 'invoice_app.db')
    print(f"Connecting to database at {db_path}...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print("Connection successful.")

        # Check if is_recurring column exists
        cursor.execute("PRAGMA table_info(invoices)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'is_recurring' not in columns:
            print("Adding 'is_recurring' column to invoices table...")
            cursor.execute("ALTER TABLE invoices ADD COLUMN is_recurring BOOLEAN")
            print("'is_recurring' column added successfully.")
        else:
            print("'is_recurring' column already exists.")

        if 'recurring_frequency' not in columns:
            print("Adding 'recurring_frequency' column to invoices table...")
            cursor.execute("ALTER TABLE invoices ADD COLUMN recurring_frequency VARCHAR")
            print("'recurring_frequency' column added successfully.")
        else:
            print("'recurring_frequency' column already exists.")

        conn.commit()
        print("Changes committed.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    add_recurring_invoice_fields() 