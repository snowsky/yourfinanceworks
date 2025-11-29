import os
import sys
import asyncio
from sqlalchemy import inspect, text

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.services.tenant_database_manager import tenant_db_manager

async def add_column_to_invoices():
    """Adds the show_discount_in_pdf column to the invoices table in all tenant databases."""
    
    tenant_dbs = tenant_db_manager.get_all_tenant_databases()

    for db_name in tenant_dbs:
        tenant_id = int(db_name.split('_')[1])
        engine = tenant_db_manager.get_tenant_engine(tenant_id)
        inspector = inspect(engine)
        
        if not 'invoices' in inspector.get_table_names():
            print(f"Table 'invoices' not found in tenant '{db_name}'. Skipping.")
            continue

        columns = [col['name'] for col in inspector.get_columns('invoices')]
        
        if 'show_discount_in_pdf' not in columns:
            print(f"Adding 'show_discount_in_pdf' to 'invoices' table in tenant '{db_name}'...")
            with engine.connect() as connection:
                connection.execute(text('ALTER TABLE invoices ADD COLUMN show_discount_in_pdf BOOLEAN DEFAULT TRUE NOT NULL'))
                connection.commit()
            print(f"Column added successfully to tenant '{db_name}'.")
        else:
            print(f"Column 'show_discount_in_pdf' already exists in 'invoices' table for tenant '{db_name}'.")

if __name__ == "__main__":
    asyncio.run(add_column_to_invoices())