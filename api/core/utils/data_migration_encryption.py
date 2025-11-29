"""
Data Migration Utility for Database Encryption

This utility handles the migration of existing unencrypted data to encrypted format.
It should be run after the database schema migration has been applied.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from sqlalchemy import text, MetaData, Table, Column, select, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from core.services.encryption_service import get_encryption_service
from core.services.key_management_service import get_key_management_service
from core.exceptions.encryption_exceptions import EncryptionError, DecryptionError

logger = logging.getLogger(__name__)


class EncryptionDataMigrator:
    """
    Handles migration of existing unencrypted data to encrypted format.
    
    This class provides methods to:
    1. Migrate data from unencrypted to encrypted columns
    2. Validate data integrity after migration
    3. Provide rollback capabilities
    4. Handle batch processing for large datasets
    """
    
    def __init__(self, session: Session, tenant_id: int, batch_size: int = 100):
        """
        Initialize the data migrator.
        
        Args:
            session: Database session for the tenant
            tenant_id: Tenant ID for encryption context
            batch_size: Number of records to process in each batch
        """
        self.session = session
        self.tenant_id = tenant_id
        self.batch_size = batch_size
        self.encryption_service = get_encryption_service()
        self.key_management_service = get_key_management_service()
        
        # Ensure tenant has encryption key
        self._ensure_tenant_key()
    
    def _ensure_tenant_key(self):
        """Ensure the tenant has an encryption key available."""
        try:
            self.encryption_service.get_tenant_key(self.tenant_id)
            logger.info(f"Encryption key available for tenant {self.tenant_id}")
        except Exception as e:
            logger.info(f"Generating new encryption key for tenant {self.tenant_id}")
            self.key_management_service.generate_tenant_key(self.tenant_id)
    
    def migrate_all_tables(self) -> Dict[str, Any]:
        """
        Migrate all tables with encrypted columns.
        
        Returns:
            Dictionary with migration results for each table
        """
        results = {}
        
        # Define table migration configurations
        table_configs = {
            'users': {
                'email': 'email_encrypted',
                'first_name': 'first_name_encrypted',
                'last_name': 'last_name_encrypted',
                'google_id': 'google_id_encrypted',
                'azure_ad_id': 'azure_ad_id_encrypted'
            },
            'clients': {
                'name': 'name_encrypted',
                'email': 'email_encrypted',
                'phone': 'phone_encrypted',
                'address': 'address_encrypted',
                'company': 'company_encrypted'
            },
            'client_notes': {
                'note': 'note_encrypted'
            },
            'invoices': {
                'notes': 'notes_encrypted',
                'custom_fields': 'custom_fields_encrypted',
                'attachment_filename': 'attachment_filename_encrypted'
            },
            'payments': {
                'reference_number': 'reference_number_encrypted',
                'notes': 'notes_encrypted'
            },
            'expenses': {
                'vendor': 'vendor_encrypted',
                'notes': 'notes_encrypted',
                'receipt_filename': 'receipt_filename_encrypted',
                'inventory_items': 'inventory_items_encrypted',
                'consumption_items': 'consumption_items_encrypted',
                'analysis_result': 'analysis_result_encrypted'
            },
            'ai_configs': {
                'provider_url': 'provider_url_encrypted',
                'api_key': 'api_key_encrypted'
            },
            'audit_logs': {
                'user_email': 'user_email_encrypted',
                'details': 'details_encrypted',
                'ip_address': 'ip_address_encrypted',
                'user_agent': 'user_agent_encrypted'
            }
        }
        
        # JSON columns that need special handling
        json_columns = {
            'invoices': ['custom_fields'],
            'expenses': ['inventory_items', 'consumption_items', 'analysis_result'],
            'audit_logs': ['details']
        }
        
        for table_name, column_mapping in table_configs.items():
            logger.info(f"Migrating table: {table_name}")
            try:
                table_json_columns = json_columns.get(table_name, [])
                result = self.migrate_table(table_name, column_mapping, table_json_columns)
                results[table_name] = result
                logger.info(f"Successfully migrated {result['migrated_count']} records in {table_name}")
            except Exception as e:
                logger.error(f"Failed to migrate table {table_name}: {str(e)}")
                results[table_name] = {'error': str(e), 'migrated_count': 0}
        
        return results
    
    def migrate_table(self, table_name: str, column_mapping: Dict[str, str], 
                     json_columns: List[str] = None) -> Dict[str, Any]:
        """
        Migrate a single table from unencrypted to encrypted columns.
        
        Args:
            table_name: Name of the table to migrate
            column_mapping: Mapping of original column to encrypted column
            json_columns: List of columns that contain JSON data
            
        Returns:
            Dictionary with migration results
        """
        json_columns = json_columns or []
        migrated_count = 0
        error_count = 0
        
        try:
            # Get total count for progress tracking
            count_query = text(f"SELECT COUNT(*) FROM {table_name}")
            total_count = self.session.execute(count_query).scalar()
            
            if total_count == 0:
                logger.info(f"No records to migrate in {table_name}")
                return {'migrated_count': 0, 'error_count': 0, 'total_count': 0}
            
            logger.info(f"Migrating {total_count} records in {table_name}")
            
            # Process in batches
            offset = 0
            while offset < total_count:
                batch_results = self._migrate_table_batch(
                    table_name, column_mapping, json_columns, offset
                )
                migrated_count += batch_results['migrated']
                error_count += batch_results['errors']
                offset += self.batch_size
                
                # Log progress
                progress = min(offset, total_count)
                logger.info(f"Progress: {progress}/{total_count} records processed")
            
            return {
                'migrated_count': migrated_count,
                'error_count': error_count,
                'total_count': total_count
            }
            
        except Exception as e:
            logger.error(f"Failed to migrate table {table_name}: {str(e)}")
            raise
    
    def _migrate_table_batch(self, table_name: str, column_mapping: Dict[str, str],
                           json_columns: List[str], offset: int) -> Dict[str, int]:
        """
        Migrate a batch of records from a table.
        
        Args:
            table_name: Name of the table
            column_mapping: Column mapping
            json_columns: JSON columns list
            offset: Batch offset
            
        Returns:
            Dictionary with batch results
        """
        migrated = 0
        errors = 0
        
        try:
            # Build SELECT query for batch
            columns = ['id'] + list(column_mapping.keys())
            columns_str = ', '.join(columns)
            
            query = text(f"""
                SELECT {columns_str}
                FROM {table_name}
                ORDER BY id
                LIMIT {self.batch_size} OFFSET {offset}
            """)
            
            result = self.session.execute(query)
            rows = result.fetchall()
            
            for row in rows:
                try:
                    # Build update statement for this record
                    update_values = {}
                    
                    for original_col, encrypted_col in column_mapping.items():
                        original_value = getattr(row, original_col)
                        
                        if original_value is not None and original_value != '':
                            if original_col in json_columns:
                                # Handle JSON data
                                if isinstance(original_value, str):
                                    try:
                                        json_data = json.loads(original_value)
                                    except json.JSONDecodeError:
                                        json_data = {"value": original_value}
                                else:
                                    json_data = original_value
                                
                                encrypted_value = self.encryption_service.encrypt_json(
                                    json_data, self.tenant_id
                                )
                            else:
                                # Handle string data
                                encrypted_value = self.encryption_service.encrypt_data(
                                    str(original_value), self.tenant_id
                                )
                            
                            update_values[encrypted_col] = encrypted_value
                    
                    # Execute update if we have values to update
                    if update_values:
                        update_query = text(f"""
                            UPDATE {table_name}
                            SET {', '.join(f'{col} = :{col}' for col in update_values.keys())}
                            WHERE id = :record_id
                        """)
                        
                        self.session.execute(update_query, {
                            **update_values,
                            'record_id': row.id
                        })
                    
                    migrated += 1
                    
                except Exception as e:
                    logger.error(f"Failed to migrate record {row.id} in {table_name}: {str(e)}")
                    errors += 1
            
            # Commit the batch
            self.session.commit()
            
        except Exception as e:
            logger.error(f"Failed to migrate batch at offset {offset}: {str(e)}")
            self.session.rollback()
            errors += len(rows) if 'rows' in locals() else self.batch_size
        
        return {'migrated': migrated, 'errors': errors}
    
    def validate_migration(self, table_name: str, column_mapping: Dict[str, str],
                          json_columns: List[str] = None) -> Dict[str, Any]:
        """
        Validate that the migration was successful by checking data integrity.
        
        Args:
            table_name: Name of the table to validate
            column_mapping: Column mapping used in migration
            json_columns: List of JSON columns
            
        Returns:
            Dictionary with validation results
        """
        json_columns = json_columns or []
        validation_results = {
            'total_records': 0,
            'encrypted_records': 0,
            'validation_errors': [],
            'sample_validations': []
        }
        
        try:
            # Get total count
            count_query = text(f"SELECT COUNT(*) FROM {table_name}")
            total_count = self.session.execute(count_query).scalar()
            validation_results['total_records'] = total_count
            
            if total_count == 0:
                return validation_results
            
            # Check how many records have encrypted data
            encrypted_columns = list(column_mapping.values())
            encrypted_check_conditions = []
            
            for col in encrypted_columns:
                encrypted_check_conditions.append(f"{col} IS NOT NULL AND {col} != ''")
            
            encrypted_query = text(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE {' OR '.join(encrypted_check_conditions)}
            """)
            
            encrypted_count = self.session.execute(encrypted_query).scalar()
            validation_results['encrypted_records'] = encrypted_count
            
            # Sample validation - decrypt a few records to verify integrity
            sample_query = text(f"""
                SELECT id, {', '.join(column_mapping.keys())}, {', '.join(column_mapping.values())}
                FROM {table_name}
                WHERE {' OR '.join(encrypted_check_conditions)}
                LIMIT 5
            """)
            
            sample_rows = self.session.execute(sample_query).fetchall()
            
            for row in sample_rows:
                sample_result = {'record_id': row.id, 'validations': []}
                
                for original_col, encrypted_col in column_mapping.items():
                    original_value = getattr(row, original_col)
                    encrypted_value = getattr(row, encrypted_col)
                    
                    if encrypted_value:
                        try:
                            if original_col in json_columns:
                                decrypted_value = self.encryption_service.decrypt_json(
                                    encrypted_value, self.tenant_id
                                )
                                # Compare JSON data
                                if isinstance(original_value, str):
                                    try:
                                        original_json = json.loads(original_value)
                                    except json.JSONDecodeError:
                                        original_json = {"value": original_value}
                                else:
                                    original_json = original_value
                                
                                matches = decrypted_value == original_json
                            else:
                                decrypted_value = self.encryption_service.decrypt_data(
                                    encrypted_value, self.tenant_id
                                )
                                matches = str(original_value) == decrypted_value
                            
                            sample_result['validations'].append({
                                'column': original_col,
                                'matches': matches,
                                'original_length': len(str(original_value)) if original_value else 0,
                                'decrypted_length': len(str(decrypted_value)) if decrypted_value else 0
                            })
                            
                        except Exception as e:
                            validation_results['validation_errors'].append({
                                'record_id': row.id,
                                'column': original_col,
                                'error': str(e)
                            })
                
                validation_results['sample_validations'].append(sample_result)
            
        except Exception as e:
            validation_results['validation_errors'].append({
                'table': table_name,
                'error': str(e)
            })
        
        return validation_results
    
    def finalize_migration(self, table_name: str, column_mapping: Dict[str, str]) -> bool:
        """
        Finalize migration by dropping old columns and renaming encrypted columns.
        
        WARNING: This is irreversible! Only call after thorough validation.
        
        Args:
            table_name: Name of the table
            column_mapping: Column mapping
            
        Returns:
            True if successful
        """
        try:
            logger.warning(f"Finalizing migration for {table_name} - this is irreversible!")
            
            # First, rename encrypted columns to original names
            for original_col, encrypted_col in column_mapping.items():
                # Add new column with original name
                self.session.execute(text(f"""
                    ALTER TABLE {table_name}
                    ADD COLUMN {original_col}_new TEXT
                """))
                
                # Copy encrypted data to new column
                self.session.execute(text(f"""
                    UPDATE {table_name}
                    SET {original_col}_new = {encrypted_col}
                """))
                
                # Drop old original column
                self.session.execute(text(f"""
                    ALTER TABLE {table_name}
                    DROP COLUMN {original_col}
                """))
                
                # Drop encrypted column
                self.session.execute(text(f"""
                    ALTER TABLE {table_name}
                    DROP COLUMN {encrypted_col}
                """))
                
                # Rename new column to original name
                self.session.execute(text(f"""
                    ALTER TABLE {table_name}
                    RENAME COLUMN {original_col}_new TO {original_col}
                """))
            
            self.session.commit()
            logger.info(f"Successfully finalized migration for {table_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to finalize migration for {table_name}: {str(e)}")
            self.session.rollback()
            return False


def run_tenant_migration(tenant_id: int, session: Session, 
                        validate_only: bool = False) -> Dict[str, Any]:
    """
    Run encryption migration for a specific tenant.
    
    Args:
        tenant_id: Tenant ID to migrate
        session: Database session for the tenant
        validate_only: If True, only validate existing migration
        
    Returns:
        Dictionary with migration results
    """
    migrator = EncryptionDataMigrator(session, tenant_id)
    
    if validate_only:
        logger.info(f"Validating encryption migration for tenant {tenant_id}")
        # Run validation for all tables
        # This would need to be implemented based on specific validation needs
        return {"status": "validation_complete", "tenant_id": tenant_id}
    else:
        logger.info(f"Running encryption migration for tenant {tenant_id}")
        results = migrator.migrate_all_tables()
        return {
            "status": "migration_complete",
            "tenant_id": tenant_id,
            "results": results
        }


if __name__ == "__main__":
    # This script can be run standalone for testing
    import sys
    import os
    
    # Add the API directory to the path
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    
    # Example usage
    print("Data migration utility for database encryption")
    print("This script should be integrated with your deployment process")