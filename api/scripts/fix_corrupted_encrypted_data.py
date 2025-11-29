#!/usr/bin/env python3
"""
Script to identify and fix corrupted encrypted data in the database.

This script will:
1. Find all encrypted columns with authentication tag verification failures
2. Attempt to decrypt data with different approaches
3. Clean up corrupted data that cannot be recovered
4. Re-encrypt data that can be recovered
"""

import os
import sys
import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# Add the API directory to Python path
sys.path.insert(0, '/app')

from sqlalchemy import create_engine, text, MetaData, Table, Column, inspect
from sqlalchemy.orm import sessionmaker
from core.services.encryption_service import EncryptionService
from core.services.key_management_service import KeyManagementService
from core.models.database import DATABASE_URL, set_tenant_context
from core.utils.column_encryptor import EncryptedColumn, EncryptedJSON
from core.exceptions.encryption_exceptions import DecryptionError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CorruptedDataFixer:
    """Tool for identifying and fixing corrupted encrypted data."""
    
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.key_management = KeyManagementService()
        self.encryption_service = EncryptionService(self.key_management)
        
        # Statistics
        self.stats = {
            'total_records_checked': 0,
            'corrupted_records_found': 0,
            'records_fixed': 0,
            'records_cleared': 0,
            'errors': []
        }
    
    def find_encrypted_tables_and_columns(self) -> Dict[str, List[str]]:
        """Find all tables and columns that use encrypted types."""
        encrypted_tables = {}
        
        # Get all table names
        inspector = inspect(self.engine)
        table_names = inspector.get_table_names()
        
        logger.info(f"Found {len(table_names)} tables to check")
        
        # For now, we'll focus on known tables with encrypted data
        # In a real implementation, you'd scan the SQLAlchemy models
        known_encrypted_tables = {
            'expenses': ['analysis_result', 'custom_fields', 'ocr_data'],
            'invoices': ['analysis_result', 'custom_fields', 'ocr_data'],
            'users': ['encrypted_settings'],
            'tenants': ['encrypted_config']
        }
        
        # Check which tables actually exist
        for table_name, columns in known_encrypted_tables.items():
            if table_name in table_names:
                # Verify columns exist
                table_columns = [col['name'] for col in inspector.get_columns(table_name)]
                existing_columns = [col for col in columns if col in table_columns]
                if existing_columns:
                    encrypted_tables[table_name] = existing_columns
                    logger.info(f"Found encrypted table: {table_name} with columns: {existing_columns}")
        
        return encrypted_tables
    
    def check_encrypted_data_in_table(self, table_name: str, columns: List[str], tenant_id: int = 1) -> List[Dict[str, Any]]:
        """Check for corrupted encrypted data in a specific table."""
        corrupted_records = []
        
        with self.SessionLocal() as session:
            # Build query to find records with encrypted data
            column_conditions = []
            for col in columns:
                column_conditions.append(f"{col} IS NOT NULL AND {col} != ''")
            
            where_clause = " OR ".join(column_conditions)
            query = text(f"""
                SELECT id, {', '.join(columns)}
                FROM {table_name}
                WHERE ({where_clause})
                ORDER BY id
                LIMIT 100
            """)
            
            try:
                results = session.execute(query).fetchall()
                logger.info(f"Found {len(results)} records with encrypted data in {table_name}")
                
                for row in results:
                    self.stats['total_records_checked'] += 1
                    record_id = row[0]
                    
                    # Check each encrypted column
                    for i, column_name in enumerate(columns):
                        column_value = row[i + 1]  # +1 because id is first
                        
                        if column_value and isinstance(column_value, str) and len(column_value) > 20:
                            # This looks like encrypted data, try to decrypt it
                            is_corrupted = self.test_decryption(column_value, tenant_id)
                            
                            if is_corrupted:
                                corrupted_records.append({
                                    'table': table_name,
                                    'id': record_id,
                                    'column': column_name,
                                    'data': column_value,
                                    'data_length': len(column_value)
                                })
                                self.stats['corrupted_records_found'] += 1
                                logger.warning(f"Found corrupted data in {table_name}.{column_name} (id={record_id})")
                
            except Exception as e:
                error_msg = f"Error checking table {table_name}: {str(e)}"
                logger.error(error_msg)
                self.stats['errors'].append(error_msg)
        
        return corrupted_records
    
    def test_decryption(self, encrypted_data: str, tenant_id: int) -> bool:
        """Test if encrypted data can be decrypted. Returns True if corrupted."""
        try:
            # Try to decrypt as JSON first
            self.encryption_service.decrypt_json(encrypted_data, tenant_id)
            return False  # Successfully decrypted
        except DecryptionError as e:
            if "Authentication tag verification failed" in str(e):
                return True  # Corrupted data
            else:
                # Other decryption errors might be recoverable
                try:
                    # Try as regular string
                    self.encryption_service.decrypt_data(encrypted_data, tenant_id)
                    return False  # Successfully decrypted
                except DecryptionError:
                    return True  # Corrupted data
        except Exception as e:
            logger.debug(f"Unexpected error during decryption test: {str(e)}")
            return True  # Assume corrupted
    
    def attempt_data_recovery(self, encrypted_data: str, tenant_id: int) -> Optional[str]:
        """Attempt to recover data using various methods."""
        
        # Method 1: Try to parse as plain JSON (maybe it was never encrypted)
        try:
            parsed = json.loads(encrypted_data)
            logger.info("Data appears to be plain JSON, not encrypted")
            return encrypted_data
        except json.JSONDecodeError:
            pass
        
        # Method 2: Check if it's a partial base64 string that can be fixed
        try:
            import base64
            # Try to fix base64 padding
            data_to_decode = encrypted_data
            missing_padding = len(encrypted_data) % 4
            if missing_padding:
                data_to_decode = encrypted_data + '=' * (4 - missing_padding)
            
            decoded = base64.b64decode(data_to_decode)
            if len(decoded) < 13:  # Too short for valid encrypted data
                logger.debug("Data too short after base64 decode")
                return None
                
        except Exception:
            logger.debug("Data is not valid base64")
            return None
        
        # Method 3: Try with different tenant keys (in case of key mix-up)
        for test_tenant_id in [1, 2, 3]:  # Test a few tenant IDs
            if test_tenant_id == tenant_id:
                continue
            try:
                decrypted = self.encryption_service.decrypt_json(encrypted_data, test_tenant_id)
                logger.info(f"Data was encrypted with tenant {test_tenant_id} key instead of {tenant_id}")
                # Re-encrypt with correct tenant key
                return self.encryption_service.encrypt_json(decrypted, tenant_id)
            except:
                continue
        
        return None  # Could not recover
    
    def fix_corrupted_record(self, record: Dict[str, Any], dry_run: bool = True) -> bool:
        """Fix a single corrupted record."""
        table_name = record['table']
        record_id = record['id']
        column_name = record['column']
        encrypted_data = record['data']
        
        logger.info(f"Attempting to fix {table_name}.{column_name} (id={record_id})")
        
        # Try to recover the data
        recovered_data = self.attempt_data_recovery(encrypted_data, tenant_id=1)
        
        if recovered_data:
            # Data was recovered, update the record
            if not dry_run:
                with self.SessionLocal() as session:
                    try:
                        update_query = text(f"""
                            UPDATE {table_name} 
                            SET {column_name} = :recovered_data 
                            WHERE id = :record_id
                        """)
                        session.execute(update_query, {
                            'recovered_data': recovered_data,
                            'record_id': record_id
                        })
                        session.commit()
                        logger.info(f"Successfully fixed {table_name}.{column_name} (id={record_id})")
                        self.stats['records_fixed'] += 1
                        return True
                    except Exception as e:
                        session.rollback()
                        error_msg = f"Failed to update {table_name}.{column_name} (id={record_id}): {str(e)}"
                        logger.error(error_msg)
                        self.stats['errors'].append(error_msg)
                        return False
            else:
                logger.info(f"DRY RUN: Would fix {table_name}.{column_name} (id={record_id})")
                return True
        else:
            # Could not recover, clear the field
            if not dry_run:
                with self.SessionLocal() as session:
                    try:
                        update_query = text(f"""
                            UPDATE {table_name} 
                            SET {column_name} = NULL 
                            WHERE id = :record_id
                        """)
                        session.execute(update_query, {'record_id': record_id})
                        session.commit()
                        logger.warning(f"Cleared corrupted data in {table_name}.{column_name} (id={record_id})")
                        self.stats['records_cleared'] += 1
                        return True
                    except Exception as e:
                        session.rollback()
                        error_msg = f"Failed to clear {table_name}.{column_name} (id={record_id}): {str(e)}"
                        logger.error(error_msg)
                        self.stats['errors'].append(error_msg)
                        return False
            else:
                logger.warning(f"DRY RUN: Would clear {table_name}.{column_name} (id={record_id})")
                return True
    
    def run_comprehensive_fix(self, dry_run: bool = True, tenant_id: int = 1):
        """Run comprehensive fix for all corrupted encrypted data."""
        logger.info(f"Starting comprehensive encrypted data fix (dry_run={dry_run})")
        
        # Set tenant context
        set_tenant_context(tenant_id)
        
        # Find all encrypted tables and columns
        encrypted_tables = self.find_encrypted_tables_and_columns()
        
        if not encrypted_tables:
            logger.info("No encrypted tables found")
            return
        
        all_corrupted_records = []
        
        # Check each table for corrupted data
        for table_name, columns in encrypted_tables.items():
            logger.info(f"Checking table: {table_name}")
            corrupted_records = self.check_encrypted_data_in_table(table_name, columns, tenant_id)
            all_corrupted_records.extend(corrupted_records)
        
        if not all_corrupted_records:
            logger.info("No corrupted encrypted data found!")
            return
        
        logger.info(f"Found {len(all_corrupted_records)} corrupted records")
        
        # Fix each corrupted record
        for record in all_corrupted_records:
            self.fix_corrupted_record(record, dry_run)
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print summary of the fix operation."""
        logger.info("\n" + "="*50)
        logger.info("CORRUPTED DATA FIX SUMMARY")
        logger.info("="*50)
        logger.info(f"Total records checked: {self.stats['total_records_checked']}")
        logger.info(f"Corrupted records found: {self.stats['corrupted_records_found']}")
        logger.info(f"Records fixed: {self.stats['records_fixed']}")
        logger.info(f"Records cleared: {self.stats['records_cleared']}")
        logger.info(f"Errors encountered: {len(self.stats['errors'])}")
        
        if self.stats['errors']:
            logger.info("\nErrors:")
            for error in self.stats['errors']:
                logger.error(f"  - {error}")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fix corrupted encrypted data')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Run in dry-run mode (default: True)')
    parser.add_argument('--execute', action='store_true', default=False,
                       help='Actually execute the fixes (overrides dry-run)')
    parser.add_argument('--tenant-id', type=int, default=1,
                       help='Tenant ID to fix data for (default: 1)')
    
    args = parser.parse_args()
    
    # If --execute is specified, turn off dry-run
    dry_run = args.dry_run and not args.execute
    
    if not dry_run:
        logger.warning("EXECUTING ACTUAL FIXES - This will modify the database!")
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Aborted by user")
            return
    
    try:
        fixer = CorruptedDataFixer()
        fixer.run_comprehensive_fix(dry_run=dry_run, tenant_id=args.tenant_id)
        
    except Exception as e:
        logger.error(f"Fix operation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()