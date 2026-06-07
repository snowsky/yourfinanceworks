"""Phase 1 of the invoice money float->Decimal migration.

Converts the invoice/payment/item money columns from double-precision float to
NUMERIC(15, 4) in every tenant database. The ``USING col::numeric(15,4)`` cast
preserves values while rounding off binary-float drift (e.g. 19.989999... -> 19.9900).

Idempotent: columns already NUMERIC are skipped. Run BEFORE deploying the model
change (the ORM maps these columns as Numeric).

    docker compose exec api python scripts/migrate_invoice_money_to_numeric.py
"""
import os
import sys
import asyncio
from sqlalchemy import inspect, text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.services.tenant_database_manager import tenant_db_manager

# table -> money columns to convert
TABLE_COLUMNS = {
    "invoices": ["amount", "subtotal", "discount_value"],
    "payments": ["amount"],
    "invoice_items": ["quantity", "price", "amount"],
}

TARGET_TYPE = "NUMERIC(15, 4)"


def _is_numeric(col_type) -> bool:
    return "NUMERIC" in str(col_type).upper() or "DECIMAL" in str(col_type).upper()


async def migrate():
    tenant_dbs = tenant_db_manager.get_all_tenant_databases()

    for db_name in tenant_dbs:
        tenant_id = int(db_name.split('_')[1])
        engine = tenant_db_manager.get_tenant_engine(tenant_id)
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        for table, columns in TABLE_COLUMNS.items():
            if table not in existing_tables:
                print(f"[{db_name}] table '{table}' not found, skipping.")
                continue

            col_types = {c['name']: c['type'] for c in inspector.get_columns(table)}
            for column in columns:
                if column not in col_types:
                    print(f"[{db_name}] {table}.{column} not found, skipping.")
                    continue
                if _is_numeric(col_types[column]):
                    print(f"[{db_name}] {table}.{column} already numeric, skipping.")
                    continue

                print(f"[{db_name}] converting {table}.{column} -> {TARGET_TYPE} ...")
                with engine.connect() as connection:
                    connection.execute(text(
                        f'ALTER TABLE {table} '
                        f'ALTER COLUMN {column} TYPE {TARGET_TYPE} '
                        f'USING {column}::numeric(15,4)'
                    ))
                    connection.commit()
                print(f"[{db_name}] {table}.{column} converted.")


if __name__ == "__main__":
    asyncio.run(migrate())
