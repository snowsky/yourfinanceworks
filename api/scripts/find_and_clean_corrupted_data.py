#!/usr/bin/env python3
"""
Simple script to find and clean corrupted encrypted data.
"""

import os
import sys
import logging

# Add the API directory to Python path
sys.path.insert(0, '/app')

from core.models.database import set_tenant_context, SessionLocal
from core.services.tenant_database_manager import tenant_db_manager
from core.services.encryption_service import EncryptionService
from core.services.key_management_service import KeyManagementService
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def find_and_clean_corrupted_data(tenant_id: int = 1, dry_run: bool = True):
    """Find and clean corrupted encrypted data for a specific tenant."""
    
    logger.info(f"Finding corrupted encrypted data for tenant {tenant_id}")
    
    # Set tenant context
    set_tenant_context(tenant_id)
    
    # Get tenant database session
    try:
        SessionLocal_tenant = tenant_db_manager.get_tenant_session(tenant_id)
    except Exception as e:
        logger.error(f"Could not get tenant session: {str(e)}")
        return
    
    # Initialize encryption service
    key_management = KeyManagementService()
    encryption_service = EncryptionService(key_management)
    
    corrupted_count = 0
    fixed_count = 0
    
    with SessionLocal_tenant() as session:
        # Check expenses table for corrupted encrypted data
        tables_to_check = [
            ('expenses', ['analysis_result']),
            ('invoices', ['custom_fields']),
            ('reminders', ['metadata']),
            ('settings', ['value']),
            ('ai_configs', ['api_key'])
        ]
        
        for table_name, columns in tables_to_check:
            logger.info(f"Checking table: {table_name}")
            
            try:
                # Get all records with encrypted data
                column_conditions = []
                for col in columns:
                    # Handle JSON columns differently
                    if col in ['metadata', 'value']:
                        column_conditions.append(f"{col} IS NOT NULL")
                    else:
                        column_conditions.append(f"{col} IS NOT NULL AND {col} != ''")
                
                where_clause = " OR ".join(column_conditions)
                query = text(f"""
                    SELECT id, {', '.join(columns)}
                    FROM {table_name}
                    WHERE ({where_clause})
                    ORDER BY id
                """)
                
                results = session.execute(query).fetchall()
                logger.info(f"Found {len(results)} records with encrypted data in {table_name}")
                
                for row in results:
                    record_id = row[0]
                    
                    # Check each encrypted column
                    for i, column_name in enumerate(columns):
                        column_value = row[i + 1]  # +1 because id is first
                        
                        # Test if this data can be decrypted
                        if column_value is not None:
                            try:
                                if column_name in ['analysis_result', 'custom_fields', 'metadata', 'value']:
                                    # These are JSON columns - check if they contain encrypted data
                                    if isinstance(column_value, str) and len(column_value) > 20:
                                        encryption_service.decrypt_json(column_value, tenant_id)
                                    elif isinstance(column_value, dict):
                                        # Already parsed JSON - skip decryption test
                                        continue
                                elif isinstance(column_value, str) and len(column_value) > 20:
                                    # Regular string columns
                                    encryption_service.decrypt_data(column_value, tenant_id)
                                
                                logger.debug(f"✓ {table_name}.{column_name} (id={record_id}) - OK")
                                
                            except Exception as e:
                                if "Authentication tag verification failed" in str(e):
                                    corrupted_count += 1
                                    logger.warning(f"✗ Found corrupted data: {table_name}.{column_name} (id={record_id})")
                                    logger.warning(f"  Data preview: {column_value[:50]}...")
                                    
                                    # Try to fix it
                                    if not dry_run:
                                        try:
                                            # Clear the corrupted data
                                            update_query = text(f"""
                                                UPDATE {table_name} 
                                                SET {column_name} = NULL 
                                                WHERE id = :record_id
                                            """)
                                            session.execute(update_query, {'record_id': record_id})
                                            session.commit()
                                            fixed_count += 1
                                            logger.info(f"  ✓ Cleared corrupted data in {table_name}.{column_name} (id={record_id})")
                                        except Exception as fix_error:
                                            session.rollback()
                                            logger.error(f"  ✗ Failed to clear data: {str(fix_error)}")
                                    else:
                                        logger.info(f"  DRY RUN: Would clear {table_name}.{column_name} (id={record_id})")
                                        fixed_count += 1
                                else:
                                    logger.debug(f"Other decryption error for {table_name}.{column_name} (id={record_id}): {str(e)}")
                
            except Exception as e:
                logger.error(f"Error checking table {table_name}: {str(e)}")
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("SUMMARY")
    logger.info("="*50)
    logger.info(f"Corrupted records found: {corrupted_count}")
    if dry_run:
        logger.info(f"Records that would be fixed: {fixed_count}")
        logger.info("Run with --execute to actually fix the data")
    else:
        logger.info(f"Records fixed: {fixed_count}")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Find and clean corrupted encrypted data')
    parser.add_argument('--execute', action='store_true', default=False,
                       help='Actually execute the fixes (default: dry-run)')
    parser.add_argument('--tenant-id', type=int, default=1,
                       help='Tenant ID to check (default: 1)')
    parser.add_argument('--force', action='store_true', default=False,
                       help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if not dry_run:
        logger.warning("EXECUTING ACTUAL FIXES - This will modify the database!")
        logger.warning("Corrupted encrypted data will be cleared (set to NULL)")
        if not args.force:
            response = input("Are you sure you want to continue? (yes/no): ")
            if response.lower() != 'yes':
                logger.info("Aborted by user")
                return
        else:
            logger.info("Force flag specified, proceeding with fixes...")
    
    try:
        find_and_clean_corrupted_data(tenant_id=args.tenant_id, dry_run=dry_run)
        
    except Exception as e:
        logger.error(f"Operation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()