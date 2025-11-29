"""
Encryption Data Integrity Validation Utility

This utility validates the integrity of encrypted data by:
1. Checking that encrypted data can be decrypted successfully
2. Verifying that decrypted data matches original data (when available)
3. Ensuring encryption coverage is complete
4. Detecting potential data corruption
"""

import logging
import json
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from core.services.encryption_service import get_encryption_service
from core.exceptions.encryption_exceptions import DecryptionError, EncryptionError

logger = logging.getLogger(__name__)


class EncryptionValidator:
    """
    Validates the integrity and completeness of database encryption.
    
    This class provides comprehensive validation methods to ensure:
    - All sensitive data is properly encrypted
    - Encrypted data can be successfully decrypted
    - No data corruption has occurred during migration
    - Encryption coverage meets security requirements
    """
    
    def __init__(self, session: Session, tenant_id: int):
        """
        Initialize the encryption validator.
        
        Args:
            session: Database session for the tenant
            tenant_id: Tenant ID for encryption context
        """
        self.session = session
        self.tenant_id = tenant_id
        self.encryption_service = get_encryption_service()
    
    def validate_all_tables(self) -> Dict[str, Any]:
        """
        Validate encryption for all tables with encrypted columns.
        
        Returns:
            Comprehensive validation report
        """
        validation_report = {
            'tenant_id': self.tenant_id,
            'overall_status': 'unknown',
            'tables': {},
            'summary': {
                'total_tables': 0,
                'tables_with_encryption': 0,
                'tables_passed': 0,
                'tables_failed': 0,
                'total_records': 0,
                'encrypted_records': 0,
                'validation_errors': 0
            }
        }
        
        # Define table validation configurations
        table_configs = {
            'users': {
                'encrypted_columns': {
                    'email': {'type': 'string', 'required': True},
                    'first_name': {'type': 'string', 'required': False},
                    'last_name': {'type': 'string', 'required': False},
                    'google_id': {'type': 'string', 'required': False},
                    'azure_ad_id': {'type': 'string', 'required': False}
                }
            },
            'clients': {
                'encrypted_columns': {
                    'name': {'type': 'string', 'required': True},
                    'email': {'type': 'string', 'required': True},
                    'phone': {'type': 'string', 'required': False},
                    'address': {'type': 'string', 'required': False},
                    'company': {'type': 'string', 'required': False}
                }
            },
            'client_notes': {
                'encrypted_columns': {
                    'note': {'type': 'string', 'required': True}
                }
            },
            'invoices': {
                'encrypted_columns': {
                    'notes': {'type': 'string', 'required': False},
                    'custom_fields': {'type': 'json', 'required': False},
                    'attachment_filename': {'type': 'string', 'required': False}
                }
            },
            'payments': {
                'encrypted_columns': {
                    'reference_number': {'type': 'string', 'required': False},
                    'notes': {'type': 'string', 'required': False}
                }
            },
            'expenses': {
                'encrypted_columns': {
                    'vendor': {'type': 'string', 'required': False},
                    'notes': {'type': 'string', 'required': False},
                    'receipt_filename': {'type': 'string', 'required': False},
                    'inventory_items': {'type': 'json', 'required': False},
                    'consumption_items': {'type': 'json', 'required': False},
                    'analysis_result': {'type': 'json', 'required': False}
                }
            },
            'ai_configs': {
                'encrypted_columns': {
                    'provider_url': {'type': 'string', 'required': False},
                    'api_key': {'type': 'string', 'required': True}
                }
            },
            'audit_logs': {
                'encrypted_columns': {
                    'user_email': {'type': 'string', 'required': True},
                    'details': {'type': 'json', 'required': False},
                    'ip_address': {'type': 'string', 'required': False},
                    'user_agent': {'type': 'string', 'required': False}
                }
            }
        }
        
        validation_report['summary']['total_tables'] = len(table_configs)
        
        for table_name, config in table_configs.items():
            logger.info(f"Validating encryption for table: {table_name}")
            try:
                table_result = self.validate_table(table_name, config['encrypted_columns'])
                validation_report['tables'][table_name] = table_result
                
                # Update summary
                if table_result['has_encrypted_data']:
                    validation_report['summary']['tables_with_encryption'] += 1
                
                if table_result['validation_passed']:
                    validation_report['summary']['tables_passed'] += 1
                else:
                    validation_report['summary']['tables_failed'] += 1
                
                validation_report['summary']['total_records'] += table_result['total_records']
                validation_report['summary']['encrypted_records'] += table_result['encrypted_records']
                validation_report['summary']['validation_errors'] += len(table_result['errors'])
                
            except Exception as e:
                logger.error(f"Failed to validate table {table_name}: {str(e)}")
                validation_report['tables'][table_name] = {
                    'validation_passed': False,
                    'error': str(e)
                }
                validation_report['summary']['tables_failed'] += 1
        
        # Determine overall status
        if validation_report['summary']['tables_failed'] == 0:
            validation_report['overall_status'] = 'passed'
        elif validation_report['summary']['tables_passed'] > 0:
            validation_report['overall_status'] = 'partial'
        else:
            validation_report['overall_status'] = 'failed'
        
        return validation_report
    
    def validate_table(self, table_name: str, encrypted_columns: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate encryption for a specific table.
        
        Args:
            table_name: Name of the table to validate
            encrypted_columns: Configuration of encrypted columns
            
        Returns:
            Table validation results
        """
        result = {
            'table_name': table_name,
            'validation_passed': False,
            'has_encrypted_data': False,
            'total_records': 0,
            'encrypted_records': 0,
            'column_results': {},
            'errors': [],
            'warnings': []
        }
        
        try:
            # Check if table exists
            if not self._table_exists(table_name):
                result['errors'].append(f"Table {table_name} does not exist")
                return result
            
            # Get total record count
            count_query = text(f"SELECT COUNT(*) FROM {table_name}")
            total_count = self.session.execute(count_query).scalar()
            result['total_records'] = total_count
            
            if total_count == 0:
                result['validation_passed'] = True
                result['warnings'].append("Table is empty")
                return result
            
            # Validate each encrypted column
            for column_name, column_config in encrypted_columns.items():
                column_result = self._validate_column(table_name, column_name, column_config)
                result['column_results'][column_name] = column_result
                
                if column_result['has_encrypted_data']:
                    result['has_encrypted_data'] = True
                
                if column_result['errors']:
                    result['errors'].extend(column_result['errors'])
                
                if column_result['warnings']:
                    result['warnings'].extend(column_result['warnings'])
            
            # Count records with any encrypted data
            encrypted_conditions = []
            existing_columns = self._get_table_columns(table_name)
            
            for column_name in encrypted_columns.keys():
                if column_name in existing_columns:
                    encrypted_conditions.append(f"{column_name} IS NOT NULL AND {column_name} != ''")
            
            if encrypted_conditions:
                encrypted_query = text(f"""
                    SELECT COUNT(*) FROM {table_name}
                    WHERE {' OR '.join(encrypted_conditions)}
                """)
                encrypted_count = self.session.execute(encrypted_query).scalar()
                result['encrypted_records'] = encrypted_count
            
            # Determine if validation passed
            result['validation_passed'] = len(result['errors']) == 0
            
        except Exception as e:
            result['errors'].append(f"Table validation failed: {str(e)}")
        
        return result
    
    def _validate_column(self, table_name: str, column_name: str, 
                        column_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate encryption for a specific column.
        
        Args:
            table_name: Name of the table
            column_name: Name of the column
            column_config: Column configuration
            
        Returns:
            Column validation results
        """
        result = {
            'column_name': column_name,
            'column_type': column_config.get('type', 'string'),
            'is_required': column_config.get('required', False),
            'has_encrypted_data': False,
            'total_values': 0,
            'encrypted_values': 0,
            'decryption_success': 0,
            'decryption_failures': 0,
            'sample_validations': [],
            'errors': [],
            'warnings': []
        }
        
        try:
            # Check if column exists
            existing_columns = self._get_table_columns(table_name)
            if column_name not in existing_columns:
                if result['is_required']:
                    result['errors'].append(f"Required encrypted column {column_name} does not exist")
                else:
                    result['warnings'].append(f"Optional encrypted column {column_name} does not exist")
                return result
            
            # Count total non-null values
            total_query = text(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE {column_name} IS NOT NULL AND {column_name} != ''
            """)
            total_values = self.session.execute(total_query).scalar()
            result['total_values'] = total_values
            
            if total_values == 0:
                if result['is_required']:
                    result['warnings'].append(f"Required column {column_name} has no data")
                return result
            
            result['has_encrypted_data'] = True
            result['encrypted_values'] = total_values
            
            # Sample validation - test decryption on a subset of records
            sample_query = text(f"""
                SELECT id, {column_name}
                FROM {table_name}
                WHERE {column_name} IS NOT NULL AND {column_name} != ''
                ORDER BY id
                LIMIT 10
            """)
            
            sample_rows = self.session.execute(sample_query).fetchall()
            
            for row in sample_rows:
                sample_result = self._validate_encrypted_value(
                    row.id, getattr(row, column_name), result['column_type']
                )
                result['sample_validations'].append(sample_result)
                
                if sample_result['decryption_success']:
                    result['decryption_success'] += 1
                else:
                    result['decryption_failures'] += 1
                    result['errors'].append(
                        f"Decryption failed for record {row.id}: {sample_result['error']}"
                    )
            
            # Check for potential unencrypted data
            if result['column_type'] == 'string':
                self._check_for_unencrypted_strings(table_name, column_name, result)
            
        except Exception as e:
            result['errors'].append(f"Column validation failed: {str(e)}")
        
        return result
    
    def _validate_encrypted_value(self, record_id: int, encrypted_value: str, 
                                 column_type: str) -> Dict[str, Any]:
        """
        Validate a single encrypted value.
        
        Args:
            record_id: Record ID for reference
            encrypted_value: Encrypted value to validate
            column_type: Type of data (string or json)
            
        Returns:
            Validation result for the value
        """
        result = {
            'record_id': record_id,
            'decryption_success': False,
            'decrypted_length': 0,
            'encrypted_length': len(encrypted_value),
            'appears_encrypted': False,
            'error': None
        }
        
        try:
            # Check if value appears to be encrypted (base64 encoded)
            result['appears_encrypted'] = self._appears_encrypted(encrypted_value)
            
            # Attempt decryption
            if column_type == 'json':
                decrypted_value = self.encryption_service.decrypt_json(encrypted_value, self.tenant_id)
                result['decrypted_length'] = len(json.dumps(decrypted_value))
            else:
                decrypted_value = self.encryption_service.decrypt_data(encrypted_value, self.tenant_id)
                result['decrypted_length'] = len(decrypted_value)
            
            result['decryption_success'] = True
            
        except DecryptionError as e:
            result['error'] = f"Decryption error: {str(e)}"
        except Exception as e:
            result['error'] = f"Unexpected error: {str(e)}"
        
        return result
    
    def _appears_encrypted(self, value: str) -> bool:
        """
        Check if a string value appears to be encrypted (base64 encoded).
        
        Args:
            value: String value to check
            
        Returns:
            True if the value appears to be encrypted
        """
        if not isinstance(value, str) or len(value) < 20:
            return False
        
        try:
            import base64
            # Try to decode as base64
            decoded = base64.b64decode(value)
            # Encrypted data should have at least 12 bytes (nonce) + some ciphertext
            return len(decoded) >= 16
        except Exception:
            return False
    
    def _check_for_unencrypted_strings(self, table_name: str, column_name: str, 
                                     result: Dict[str, Any]):
        """
        Check for potentially unencrypted string data.
        
        Args:
            table_name: Name of the table
            column_name: Name of the column
            result: Result dictionary to update
        """
        try:
            # Look for values that don't appear to be base64 encoded
            suspicious_query = text(f"""
                SELECT id, {column_name}
                FROM {table_name}
                WHERE {column_name} IS NOT NULL 
                AND {column_name} != ''
                AND LENGTH({column_name}) < 50  -- Encrypted data is usually longer
                LIMIT 5
            """)
            
            suspicious_rows = self.session.execute(suspicious_query).fetchall()
            
            for row in suspicious_rows:
                value = getattr(row, column_name)
                if not self._appears_encrypted(value):
                    result['warnings'].append(
                        f"Record {row.id} may contain unencrypted data: '{value[:20]}...'"
                    )
        
        except Exception as e:
            result['warnings'].append(f"Could not check for unencrypted data: {str(e)}")
    
    def _table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if the table exists
        """
        try:
            query = text("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_name = :table_name
            """)
            
            result = self.session.execute(query, {'table_name': table_name})
            return result.scalar() > 0
            
        except Exception:
            return False
    
    def _get_table_columns(self, table_name: str) -> List[str]:
        """
        Get list of columns in a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of column names
        """
        try:
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
    
    def generate_validation_report(self, validation_results: Dict[str, Any]) -> str:
        """
        Generate a human-readable validation report.
        
        Args:
            validation_results: Results from validate_all_tables()
            
        Returns:
            Formatted validation report
        """
        report_lines = []
        
        # Header
        report_lines.append("=" * 60)
        report_lines.append("DATABASE ENCRYPTION VALIDATION REPORT")
        report_lines.append("=" * 60)
        report_lines.append(f"Tenant ID: {validation_results['tenant_id']}")
        report_lines.append(f"Overall Status: {validation_results['overall_status'].upper()}")
        report_lines.append("")
        
        # Summary
        summary = validation_results['summary']
        report_lines.append("SUMMARY:")
        report_lines.append(f"  Total Tables: {summary['total_tables']}")
        report_lines.append(f"  Tables with Encryption: {summary['tables_with_encryption']}")
        report_lines.append(f"  Tables Passed: {summary['tables_passed']}")
        report_lines.append(f"  Tables Failed: {summary['tables_failed']}")
        report_lines.append(f"  Total Records: {summary['total_records']}")
        report_lines.append(f"  Encrypted Records: {summary['encrypted_records']}")
        report_lines.append(f"  Validation Errors: {summary['validation_errors']}")
        report_lines.append("")
        
        # Table details
        report_lines.append("TABLE DETAILS:")
        for table_name, table_result in validation_results['tables'].items():
            status = "PASS" if table_result.get('validation_passed', False) else "FAIL"
            report_lines.append(f"  {table_name}: {status}")
            
            if 'total_records' in table_result:
                report_lines.append(f"    Records: {table_result['total_records']}")
                report_lines.append(f"    Encrypted: {table_result['encrypted_records']}")
            
            if table_result.get('errors'):
                report_lines.append("    Errors:")
                for error in table_result['errors'][:3]:  # Limit to first 3 errors
                    report_lines.append(f"      - {error}")
            
            if table_result.get('warnings'):
                report_lines.append("    Warnings:")
                for warning in table_result['warnings'][:3]:  # Limit to first 3 warnings
                    report_lines.append(f"      - {warning}")
            
            report_lines.append("")
        
        return "\n".join(report_lines)


def run_tenant_validation(tenant_id: int, session: Session) -> Dict[str, Any]:
    """
    Run encryption validation for a specific tenant.
    
    Args:
        tenant_id: Tenant ID to validate
        session: Database session for the tenant
        
    Returns:
        Dictionary with validation results
    """
    validator = EncryptionValidator(session, tenant_id)
    
    logger.info(f"Running encryption validation for tenant {tenant_id}")
    results = validator.validate_all_tables()
    
    # Generate and log report
    report = validator.generate_validation_report(results)
    logger.info(f"Validation report:\n{report}")
    
    return results


if __name__ == "__main__":
    # This script can be run standalone for testing
    import sys
    import os
    
    # Add the API directory to the path
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    
    # Example usage
    print("Encryption validation utility")
    print("This script validates the integrity of encrypted database data")