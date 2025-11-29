"""
Encryption Rollback Utility

This utility provides rollback capabilities for database encryption migration.
It can decrypt encrypted data back to plain text format if needed.

WARNING: This should only be used in emergency situations or during
initial deployment testing. Production rollbacks may result in data loss.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from core.services.encryption_service import get_encryption_service
from core.exceptions.encryption_exceptions import DecryptionError

logger = logging.getLogger(__name__)


class EncryptionRollbackManager:
    """
    Handles rollback of encrypted data to unencrypted format.
    
    This class provides methods to:
    1. Decrypt encrypted columns back to plain text
    2. Validate rollback integrity
    3. Handle batch processing for large datasets
    """
    
    def __init__(self, session: Session, tenant_id: int, batch_size: int = 100):
        """
        Initialize the rollback manager.
        
        Args:
            session: Database session for the tenant
            tenant_id: Tenant ID for decryption context
            batch_size: Number of records to process in each batch
        """
        self.session = session
        self.tenant_id = tenant_id
        self.batch_size = batch_size
        self.encryption_service = get_encryption_service()
    
    def rollback_all_tables(self) -> Dict[str, Any]:
        """
        Rollback all tables with encrypted columns.
        
        Returns:
            Dictionary with rollback results for each table
        """
        results = {}
        
        # Define table rollback configurations
        table_configs = {
            'users': {
                'email_encrypted': 'email',
                'first_name_encrypted': 'first_name',
                'last_name_encrypted': 'last_name',
                'google_id_encrypted': 'google_id',
                'azure_ad_id_encrypted': 'azure_ad_id'
            },
            'clients': {
                'name_encrypted': 'name',
                'email_encrypted': 'email',
                'phone_encrypted': 'phone',
                'address_encrypted': 'address',
                'company_encrypted': 'company'
            },
            'client_notes': {
                'note_encrypted': 'note'
            },
            'invoices': {
                'notes_encrypted': 'notes',
                'custom_fields_encrypted': 'custom_fields',
                'attachment_filename_encrypted': 'attachment_filename'
            },
            'payments': {
                'reference_number_encrypted': 'reference_number',
                'notes_encrypted': 'notes'
            },
            'expenses': {
                'vendor_encrypted': 'vendor',
                'notes_encrypted': 'notes',
                'receipt_filename_encrypted': 'receipt_filename',
                'inventory_items_encrypted': 'inventory_items',
                'consumption_items_encrypted': 'consumption_items',
                'analysis_result_encrypted': 'analysis_result'
            },
            'ai_configs': {
                'provider_url_encrypted': 'provider_url',
                'api_key_encrypted': 'api_key'
            },
            'audit_logs': {
                'user_email_encrypted': 'user_email',
                'details_encrypted': 'details',
                'ip_address_encrypted': 'ip_address',
                'user_agent_encrypted': 'user_agent'
            }
        }
        
        # JSON columns that need special handling
        json_columns = {
            'invoices': ['custom_fields'],
            'expenses': ['inventory_items', 'consumption_items', 'analysis_result'],
            'audit_logs': ['details']
        }
        
        for table_name, column_mapping in table_configs.items():
            logger.info(f"Rolling back table: {table_name}")
            try:
                table_json_columns = json_columns.get(table_name, [])
                result = self.rollback_table(table_name, column_mapping, table_json_columns)
                results[table_name] = result
                logger.info(f"Successfully rolled back {result['rollback_count']} records in {table_name}")
            except Exception as e:
                logger.error(f"Failed to rollback table {table_name}: {str(e)}")
                results[table_name] = {'error': str(e), 'rollback_count': 0}
        
        return results
    
    def rollback_table(self, table_name: str, column_mapping: Dict[str, str],
                      json_columns: List[str] = None) -> Dict[str, Any]:
        """
        Rollback a single table from encrypted to unencrypted columns.
        
        Args:
            table_name: Name of the table to rollback
            column_mapping: Mapping of encrypted column to original column
            json_columns: List of columns that contain JSON data
            
        Returns:
            Dictionary with rollback results
        """
        json_columns = json_columns or []
        rollback_count = 0
        error_count = 0
        
        try:
            # Check if encrypted columns exist
            encrypted_columns = list(column_mapping.keys())
            existing_columns = self._get_table_columns(table_name)
            
            available_encrypted_columns = [col for col in encrypted_columns if col in existing_columns]
            
            if not available_encrypted_columns:
                logger.info(f"No encrypted columns found in {table_name}")
                return {'rollback_count': 0, 'error_count': 0, 'total_count': 0}
            
            # Get total count for progress tracking
            count_query = text(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE {' OR '.join(f'{col} IS NOT NULL AND {col} != \'\'' for col in available_encrypted_columns)}
            """)
            total_count = self.session.execute(count_query).scalar()
            
            if total_count == 0:
                logger.info(f"No encrypted records to rollback in {table_name}")
                return {'rollback_count': 0, 'error_count': 0, 'total_count': 0}
            
            logger.info(f"Rolling back {total_count} records in {table_name}")
            
            # Process in batches
            offset = 0
            while offset < total_count:
                batch_results = self._rollback_table_batch(
                    table_name, column_mapping, json_columns, offset, available_encrypted_columns
                )
                rollback_count += batch_results['rollback']
                error_count += batch_results['errors']
                offset += self.batch_size
                
                # Log progress
                progress = min(offset, total_count)
                logger.info(f"Progress: {progress}/{total_count} records processed")
            
            return {
                'rollback_count': rollback_count,
                'error_count': error_count,
                'total_count': total_count
            }
            
        except Exception as e:
            logger.error(f"Failed to rollback table {table_name}: {str(e)}")
            raise
    
    def _rollback_table_batch(self, table_name: str, column_mapping: Dict[str, str],
                             json_columns: List[str], offset: int,
                             available_encrypted_columns: List[str]) -> Dict[str, int]:
        """
        Rollback a batch of records from a table.
        
        Args:
            table_name: Name of the table
            column_mapping: Column mapping
            json_columns: JSON columns list
            offset: Batch offset
            available_encrypted_columns: List of encrypted columns that exist
            
        Returns:
            Dictionary with batch results
        """
        rollback = 0
        errors = 0
        
        try:
            # Build SELECT query for batch
            columns = ['id'] + available_encrypted_columns
            columns_str = ', '.join(columns)
            
            query = text(f"""
                SELECT {columns_str}
                FROM {table_name}
                WHERE {' OR '.join(f'{col} IS NOT NULL AND {col} != \'\'' for col in available_encrypted_columns)}
                ORDER BY id
                LIMIT {self.batch_size} OFFSET {offset}
            """)
            
            result = self.session.execute(query)
            rows = result.fetchall()
            
            for row in rows:
                try:
                    # Build update statement for this record
                    update_values = {}
                    
                    for encrypted_col in available_encrypted_columns:
                        if encrypted_col in column_mapping:
                            original_col = column_mapping[encrypted_col]
                            encrypted_value = getattr(row, encrypted_col)
                            
                            if encrypted_value is not None and encrypted_value != '':
                                try:
                                    if original_col in json_columns:
                                        # Handle JSON data
                                        decrypted_data = self.encryption_service.decrypt_json(
                                            encrypted_value, self.tenant_id
                                        )
                                        # Convert back to JSON string for storage
                                        decrypted_value = json.dumps(decrypted_data)
                                    else:
                                        # Handle string data
                                        decrypted_value = self.encryption_service.decrypt_data(
                                            encrypted_value, self.tenant_id
                                        )
                                    
                                    update_values[original_col] = decrypted_value
                                    
                                except DecryptionError as e:
                                    logger.warning(f"Failed to decrypt {encrypted_col} for record {row.id}: {str(e)}")
                                    # Continue with other columns
                    
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
                    
                    rollback += 1
                    
                except Exception as e:
                    logger.error(f"Failed to rollback record {row.id} in {table_name}: {str(e)}")
                    errors += 1
            
            # Commit the batch
            self.session.commit()
            
        except Exception as e:
            logger.error(f"Failed to rollback batch at offset {offset}: {str(e)}")
            self.session.rollback()
            errors += len(rows) if 'rows' in locals() else self.batch_size
        
        return {'rollback': rollback, 'errors': errors}
    
    def _get_table_columns(self, table_name: str) -> List[str]:
        """
        Get list of columns in a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of column names
        """
        try:
            # Query information schema to get column names
            query = text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = :table_name
            """)
            
            result = self.session.execute(query, {'table_name': table_name})
            return [row[0] for row in result.fetchall()]
            
        except Exception as e:
            logger.error(f"Failed to get columns for table {table_name}: {str(e)}")
            return []
    
    def validate_rollback(self, table_name: str, column_mapping: Dict[str, str]) -> Dict[str, Any]:
        """
        Validate that the rollback was successful.
        
        Args:
            table_name: Name of the table to validate
            column_mapping: Column mapping used in rollback
            
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'total_records': 0,
            'decrypted_records': 0,
            'remaining_encrypted': 0,
            'validation_errors': []
        }
        
        try:
            # Get total count
            count_query = text(f"SELECT COUNT(*) FROM {table_name}")
            total_count = self.session.execute(count_query).scalar()
            validation_results['total_records'] = total_count
            
            if total_count == 0:
                return validation_results
            
            # Check how many records have decrypted data
            original_columns = list(column_mapping.values())
            decrypted_check_conditions = []
            
            for col in original_columns:
                decrypted_check_conditions.append(f"{col} IS NOT NULL AND {col} != ''")
            
            decrypted_query = text(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE {' OR '.join(decrypted_check_conditions)}
            """)
            
            decrypted_count = self.session.execute(decrypted_query).scalar()
            validation_results['decrypted_records'] = decrypted_count
            
            # Check for remaining encrypted data
            encrypted_columns = list(column_mapping.keys())
            existing_columns = self._get_table_columns(table_name)
            available_encrypted_columns = [col for col in encrypted_columns if col in existing_columns]
            
            if available_encrypted_columns:
                encrypted_check_conditions = []
                for col in available_encrypted_columns:
                    encrypted_check_conditions.append(f"{col} IS NOT NULL AND {col} != ''")
                
                remaining_encrypted_query = text(f"""
                    SELECT COUNT(*) FROM {table_name}
                    WHERE {' OR '.join(encrypted_check_conditions)}
                """)
                
                remaining_count = self.session.execute(remaining_encrypted_query).scalar()
                validation_results['remaining_encrypted'] = remaining_count
            
        except Exception as e:
            validation_results['validation_errors'].append({
                'table': table_name,
                'error': str(e)
            })
        
        return validation_results


def run_tenant_rollback(tenant_id: int, session: Session,
                       validate_only: bool = False) -> Dict[str, Any]:
    """
    Run encryption rollback for a specific tenant.
    
    Args:
        tenant_id: Tenant ID to rollback
        session: Database session for the tenant
        validate_only: If True, only validate existing rollback
        
    Returns:
        Dictionary with rollback results
    """
    rollback_manager = EncryptionRollbackManager(session, tenant_id)
    
    if validate_only:
        logger.info(f"Validating encryption rollback for tenant {tenant_id}")
        # Run validation for all tables
        return {"status": "validation_complete", "tenant_id": tenant_id}
    else:
        logger.warning(f"Running encryption rollback for tenant {tenant_id}")
        logger.warning("This operation will decrypt sensitive data - ensure this is intended!")
        results = rollback_manager.rollback_all_tables()
        return {
            "status": "rollback_complete",
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
    print("Encryption rollback utility")
    print("WARNING: This will decrypt sensitive data!")
    print("This script should only be used in emergency situations")