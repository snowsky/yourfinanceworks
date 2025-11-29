#!/usr/bin/env python3
"""
Data migration script to encrypt existing plain text data.

This script identifies plain text data in encrypted columns and encrypts it
using the current encryption configuration.
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Dict, Any
import re

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.orm import sessionmaker
from core.models.database import get_database_url
from core.services.encryption_service import get_encryption_service
from encryption_config import EncryptionConfig
from core.utils.column_encryptor import is_encrypted_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataMigrationService:
    """Service for migrating plain text data to encrypted format."""
    
    def __init__(self):
        self.config = EncryptionConfig()
        if not self.config.ENCRYPTION_ENABLED:
            raise ValueError("Encryption must be enabled to run migration")
        
        self.encryption_service = get_encryption_service()
        
        # Connect to master database
        database_url = get_database_url()
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        
        logger.info("Data migration service initialized")
    
    def identify_encrypted_columns(self) -> Dict[str, List[str]]:
        """
        Identify tables and columns that should be encrypted.
        
        Returns:
            Dictionary mapping table names to lists of encrypted column names
        """
        # Define which columns should be encrypted based on the model definitions
        encrypted_columns = {
            'tenants': ['name', 'email', 'phone', 'address'],
            'users': ['email', 'first_name', 'last_name'],
            'clients': ['name', 'email', 'phone', 'address'],
            # Add more tables as needed
        }
        
        return encrypted_columns
    
    def is_plain_text_data(self, value: str) -> bool:
        """
        Check if a value appears to be plain text (not encrypted).
        
        Args:
            value: The value to check
            
        Returns:
            True if it appears to be plain text, False if encrypted
        """
        if not value or not isinstance(value, str):
            return False
        
        # If it's already encrypted data, skip it
        if is_encrypted_data(value):
            return False
        
        # Check for common plain text patterns
        if '@' in value and '.' in value:  # Email pattern
            return True
        if value.isalpha() or value.replace(' ', '').isalpha():  # Text names
            return True
        if len(value) < 30 and not re.match(r'^[A-Za-z0-9+/]+=*$', value):  # Short non-base64
            return True
        
        return True
    
    def migrate_table_data(self, table_name: str, columns: List[str], tenant_id: int = 1) -> Dict[str, Any]:
        """
        Migrate plain text data in a table to encrypted format.
        
        Args:
            table_name: Name of the table to migrate
            columns: List of column names to encrypt
            tenant_id: Tenant ID for encryption context
            
        Returns:
            Dictionary with migration results
        """
        results = {
            'table': table_name,
            'total_rows': 0,
            'migrated_rows': 0,
            'skipped_rows': 0,
            'errors': []
        }
        
        try:
            with self.Session() as session:
                # Get all rows from the table
                query = text(f"SELECT * FROM {table_name}")
                rows = session.execute(query).fetchall()
                results['total_rows'] = len(rows)
                
                logger.info(f"Processing {len(rows)} rows in table {table_name}")
                
                for row in rows:
                    row_dict = dict(row._mapping)
                    row_id = row_dict.get('id')
                    needs_update = False
                    update_values = {}
                    
                    # Check each encrypted column
                    for column in columns:
                        if column in row_dict:
                            value = row_dict[column]
                            
                            if value and self.is_plain_text_data(str(value)):
                                try:
                                    # Encrypt the plain text value
                                    encrypted_value = self.encryption_service.encrypt_data(str(value), tenant_id)
                                    update_values[column] = encrypted_value
                                    needs_update = True
                                    logger.debug(f"Will encrypt {column} for row {row_id}")
                                except Exception as e:
                                    error_msg = f"Failed to encrypt {column} for row {row_id}: {str(e)}"
                                    logger.error(error_msg)
                                    results['errors'].append(error_msg)
                    
                    # Update the row if needed
                    if needs_update:
                        try:
                            set_clause = ", ".join([f"{col} = :{col}" for col in update_values.keys()])
                            update_query = text(f"UPDATE {table_name} SET {set_clause} WHERE id = :row_id")
                            
                            params = update_values.copy()
                            params['row_id'] = row_id
                            
                            session.execute(update_query, params)
                            session.commit()
                            
                            results['migrated_rows'] += 1
                            logger.info(f"Migrated row {row_id} in table {table_name}")
                            
                        except Exception as e:
                            session.rollback()
                            error_msg = f"Failed to update row {row_id} in table {table_name}: {str(e)}"
                            logger.error(error_msg)
                            results['errors'].append(error_msg)
                    else:
                        results['skipped_rows'] += 1
                        logger.debug(f"Skipped row {row_id} in table {table_name} (already encrypted or no data)")
                
        except Exception as e:
            error_msg = f"Failed to migrate table {table_name}: {str(e)}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
        
        return results
    
    def run_migration(self, tenant_id: int = 1) -> Dict[str, Any]:
        """
        Run the complete data migration process.
        
        Args:
            tenant_id: Tenant ID for encryption context
            
        Returns:
            Dictionary with overall migration results
        """
        logger.info(f"Starting data migration for tenant {tenant_id}")
        
        overall_results = {
            'tenant_id': tenant_id,
            'tables_processed': 0,
            'total_rows': 0,
            'total_migrated': 0,
            'total_skipped': 0,
            'total_errors': 0,
            'table_results': []
        }
        
        encrypted_columns = self.identify_encrypted_columns()
        
        for table_name, columns in encrypted_columns.items():
            logger.info(f"Migrating table: {table_name}, columns: {columns}")
            
            try:
                table_results = self.migrate_table_data(table_name, columns, tenant_id)
                overall_results['table_results'].append(table_results)
                overall_results['tables_processed'] += 1
                overall_results['total_rows'] += table_results['total_rows']
                overall_results['total_migrated'] += table_results['migrated_rows']
                overall_results['total_skipped'] += table_results['skipped_rows']
                overall_results['total_errors'] += len(table_results['errors'])
                
            except Exception as e:
                error_msg = f"Failed to process table {table_name}: {str(e)}"
                logger.error(error_msg)
                overall_results['total_errors'] += 1
        
        logger.info("Data migration completed")
        logger.info(f"Summary: {overall_results['total_migrated']} rows migrated, "
                   f"{overall_results['total_skipped']} rows skipped, "
                   f"{overall_results['total_errors']} errors")
        
        return overall_results
    
    def verify_migration(self, tenant_id: int = 1) -> Dict[str, Any]:
        """
        Verify that the migration was successful by checking for remaining plain text data.
        
        Args:
            tenant_id: Tenant ID for verification
            
        Returns:
            Dictionary with verification results
        """
        logger.info(f"Verifying migration for tenant {tenant_id}")
        
        verification_results = {
            'tenant_id': tenant_id,
            'tables_checked': 0,
            'plain_text_found': [],
            'verification_passed': True
        }
        
        encrypted_columns = self.identify_encrypted_columns()
        
        for table_name, columns in encrypted_columns.items():
            try:
                with self.Session() as session:
                    query = text(f"SELECT * FROM {table_name}")
                    rows = session.execute(query).fetchall()
                    
                    for row in rows:
                        row_dict = dict(row._mapping)
                        row_id = row_dict.get('id')
                        
                        for column in columns:
                            if column in row_dict:
                                value = row_dict[column]
                                
                                if value and self.is_plain_text_data(str(value)):
                                    plain_text_entry = {
                                        'table': table_name,
                                        'row_id': row_id,
                                        'column': column,
                                        'value': str(value)[:50] + '...' if len(str(value)) > 50 else str(value)
                                    }
                                    verification_results['plain_text_found'].append(plain_text_entry)
                                    verification_results['verification_passed'] = False
                
                verification_results['tables_checked'] += 1
                
            except Exception as e:
                logger.error(f"Failed to verify table {table_name}: {str(e)}")
                verification_results['verification_passed'] = False
        
        if verification_results['verification_passed']:
            logger.info("Migration verification passed - no plain text data found")
        else:
            logger.warning(f"Migration verification failed - found {len(verification_results['plain_text_found'])} plain text entries")
        
        return verification_results


def main():
    """Main migration function."""
    try:
        logger.info("Starting data migration to encryption")
        
        # Initialize migration service
        migration_service = DataMigrationService()
        
        # Run migration for tenant 1 (default tenant)
        results = migration_service.run_migration(tenant_id=1)
        
        # Print results
        print("\n" + "="*60)
        print("MIGRATION RESULTS")
        print("="*60)
        print(f"Tenant ID: {results['tenant_id']}")
        print(f"Tables processed: {results['tables_processed']}")
        print(f"Total rows: {results['total_rows']}")
        print(f"Rows migrated: {results['total_migrated']}")
        print(f"Rows skipped: {results['total_skipped']}")
        print(f"Errors: {results['total_errors']}")
        
        if results['total_errors'] > 0:
            print("\nErrors encountered:")
            for table_result in results['table_results']:
                for error in table_result['errors']:
                    print(f"  - {error}")
        
        # Verify migration
        verification = migration_service.verify_migration(tenant_id=1)
        
        print("\n" + "="*60)
        print("VERIFICATION RESULTS")
        print("="*60)
        print(f"Verification passed: {verification['verification_passed']}")
        
        if not verification['verification_passed']:
            print(f"Plain text entries found: {len(verification['plain_text_found'])}")
            for entry in verification['plain_text_found']:
                print(f"  - {entry['table']}.{entry['column']} (row {entry['row_id']}): {entry['value']}")
        
        print("="*60)
        
        if results['total_errors'] == 0 and verification['verification_passed']:
            logger.info("Data migration completed successfully")
            sys.exit(0)
        else:
            logger.error("Data migration completed with errors")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()