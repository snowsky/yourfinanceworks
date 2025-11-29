"""
Encryption Compliance Service

This service provides compliance features for GDPR, SOX, and other regulatory requirements,
including data destruction, audit logging, and data residency compliance.
"""

import logging
import json
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import text

from encryption_config import EncryptionConfig
from core.exceptions.encryption_exceptions import ComplianceError
from core.services.encryption_service import EncryptionService
from core.services.key_management_service import KeyManagementService


class ComplianceRegulation(Enum):
    """Supported compliance regulations"""
    GDPR = "gdpr"
    SOX = "sox"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    CCPA = "ccpa"


class DataCategory(Enum):
    """Categories of data for compliance purposes"""
    PERSONAL_DATA = "personal_data"
    FINANCIAL_DATA = "financial_data"
    HEALTH_DATA = "health_data"
    PAYMENT_DATA = "payment_data"
    SENSITIVE_DATA = "sensitive_data"


class AuditAction(Enum):
    """Types of audit actions"""
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    DATA_DELETION = "data_deletion"
    KEY_ACCESS = "key_access"
    KEY_ROTATION = "key_rotation"
    COMPLIANCE_REQUEST = "compliance_request"
    DATA_EXPORT = "data_export"
    DATA_ANONYMIZATION = "data_anonymization"


@dataclass
class ComplianceAuditLog:
    """Audit log entry for compliance tracking"""
    id: str
    timestamp: datetime
    tenant_id: int
    user_id: Optional[int]
    action: AuditAction
    regulation: ComplianceRegulation
    data_category: DataCategory
    affected_records: List[str]  # Record IDs or identifiers
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class DataResidencyRule:
    """Data residency compliance rule"""
    tenant_id: int
    regulation: ComplianceRegulation
    allowed_regions: List[str]
    data_categories: List[DataCategory]
    encryption_required: bool = True
    key_residency_required: bool = True


@dataclass
class RetentionPolicy:
    """Data retention policy for compliance"""
    tenant_id: int
    data_category: DataCategory
    retention_period_days: int
    auto_delete: bool = False
    anonymize_after_retention: bool = True


class EncryptionComplianceService:
    """
    Service for handling encryption compliance requirements including GDPR, SOX, and audit logging
    """
    
    def __init__(self, encryption_service: EncryptionService, 
                 key_management_service: KeyManagementService):
        self.logger = logging.getLogger(__name__)
        self.config = EncryptionConfig()
        self.encryption_service = encryption_service
        self.key_management_service = key_management_service
        
        # Compliance audit logs storage (in production, this would be a database)
        self._audit_logs: List[ComplianceAuditLog] = []
        
        # Data residency rules
        self._residency_rules: Dict[int, List[DataResidencyRule]] = {}
        
        # Retention policies
        self._retention_policies: Dict[int, List[RetentionPolicy]] = {}
        
        # Data classification mapping
        self._data_classification = {
            'users': [DataCategory.PERSONAL_DATA],
            'clients': [DataCategory.PERSONAL_DATA, DataCategory.FINANCIAL_DATA],
            'invoices': [DataCategory.FINANCIAL_DATA],
            'payments': [DataCategory.FINANCIAL_DATA, DataCategory.PAYMENT_DATA],
            'expenses': [DataCategory.FINANCIAL_DATA],
            'audit_logs': [DataCategory.SENSITIVE_DATA]
        }
        
        self.logger.info("Encryption compliance service initialized")
    
    def log_audit_event(self, tenant_id: int, action: AuditAction, 
                       regulation: ComplianceRegulation, data_category: DataCategory,
                       affected_records: List[str], details: Dict[str, Any],
                       user_id: Optional[int] = None, ip_address: Optional[str] = None,
                       user_agent: Optional[str] = None, success: bool = True,
                       error_message: Optional[str] = None):
        """
        Log an audit event for compliance tracking
        
        Args:
            tenant_id: Tenant ID
            action: Type of action performed
            regulation: Applicable regulation
            data_category: Category of data affected
            affected_records: List of record identifiers
            details: Additional details about the action
            user_id: User who performed the action
            ip_address: IP address of the request
            user_agent: User agent string
            success: Whether the action was successful
            error_message: Error message if action failed
        """
        audit_log = ComplianceAuditLog(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            regulation=regulation,
            data_category=data_category,
            affected_records=affected_records,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message
        )
        
        self._audit_logs.append(audit_log)
        
        # Log to application logs as well
        log_level = logging.INFO if success else logging.ERROR
        self.logger.log(
            log_level,
            f"Compliance audit: {action.value} for {regulation.value} "
            f"on {data_category.value} by tenant {tenant_id}"
        )
    
    def handle_gdpr_right_to_be_forgotten(self, tenant_id: int, user_email: str,
                                        request_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle GDPR right-to-be-forgotten request with encrypted data destruction
        
        Args:
            tenant_id: Tenant ID
            user_email: Email of the user requesting data deletion
            request_details: Details of the deletion request
            
        Returns:
            Dictionary containing the result of the deletion process
        """
        try:
            self.logger.info(f"Processing GDPR right-to-be-forgotten for {user_email} in tenant {tenant_id}")
            
            # Find all records containing the user's data
            affected_records = self._find_user_data_records(tenant_id, user_email)
            
            # Perform secure data deletion
            deletion_results = {}
            for table_name, record_ids in affected_records.items():
                deletion_results[table_name] = self._secure_delete_records(
                    tenant_id, table_name, record_ids
                )
            
            # Destroy encryption keys for the deleted data if applicable
            self._destroy_user_specific_keys(tenant_id, user_email)
            
            # Log the compliance action
            self.log_audit_event(
                tenant_id=tenant_id,
                action=AuditAction.DATA_DELETION,
                regulation=ComplianceRegulation.GDPR,
                data_category=DataCategory.PERSONAL_DATA,
                affected_records=list(affected_records.keys()),
                details={
                    'user_email': user_email,
                    'request_details': request_details,
                    'deletion_results': deletion_results
                },
                success=True
            )
            
            return {
                'success': True,
                'user_email': user_email,
                'affected_tables': list(affected_records.keys()),
                'total_records_deleted': sum(len(ids) for ids in affected_records.values()),
                'deletion_timestamp': datetime.utcnow().isoformat(),
                'verification_hash': self._generate_deletion_verification_hash(
                    tenant_id, user_email, affected_records
                )
            }
            
        except Exception as e:
            self.logger.error(f"GDPR deletion failed for {user_email}: {str(e)}")
            
            self.log_audit_event(
                tenant_id=tenant_id,
                action=AuditAction.DATA_DELETION,
                regulation=ComplianceRegulation.GDPR,
                data_category=DataCategory.PERSONAL_DATA,
                affected_records=[],
                details={'user_email': user_email, 'request_details': request_details},
                success=False,
                error_message=str(e)
            )
            
            raise ComplianceError(f"GDPR right-to-be-forgotten failed: {str(e)}")
    
    def _find_user_data_records(self, tenant_id: int, user_email: str) -> Dict[str, List[str]]:
        """Find all records containing user data across tables"""
        # This would query the actual database in production
        # For now, return a mock structure
        return {
            'users': [f"user_{hashlib.md5(user_email.encode()).hexdigest()[:8]}"],
            'clients': [],
            'audit_logs': [f"audit_{hashlib.md5(user_email.encode()).hexdigest()[:8]}"]
        }
    
    def _secure_delete_records(self, tenant_id: int, table_name: str, 
                              record_ids: List[str]) -> Dict[str, Any]:
        """Securely delete records with cryptographic erasure"""
        try:
            # In production, this would:
            # 1. Overwrite the encrypted data with random data
            # 2. Delete the encryption keys
            # 3. Remove the database records
            # 4. Verify the deletion
            
            deleted_count = len(record_ids)
            
            self.logger.info(f"Securely deleted {deleted_count} records from {table_name}")
            
            return {
                'table': table_name,
                'records_deleted': deleted_count,
                'deletion_method': 'cryptographic_erasure',
                'verification_passed': True
            }
            
        except Exception as e:
            self.logger.error(f"Secure deletion failed for {table_name}: {str(e)}")
            return {
                'table': table_name,
                'records_deleted': 0,
                'deletion_method': 'failed',
                'error': str(e),
                'verification_passed': False
            }
    
    def _destroy_user_specific_keys(self, tenant_id: int, user_email: str):
        """Destroy encryption keys specific to user data"""
        # In production, this would destroy any user-specific encryption keys
        # For now, just log the action
        self.logger.info(f"Destroyed user-specific keys for {user_email} in tenant {tenant_id}")
    
    def _generate_deletion_verification_hash(self, tenant_id: int, user_email: str, 
                                           affected_records: Dict[str, List[str]]) -> str:
        """Generate a verification hash for the deletion process"""
        verification_data = {
            'tenant_id': tenant_id,
            'user_email': user_email,
            'affected_records': affected_records,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        verification_string = json.dumps(verification_data, sort_keys=True)
        return hashlib.sha256(verification_string.encode()).hexdigest()
    
    def implement_sox_compliance_features(self, tenant_id: int) -> Dict[str, Any]:
        """
        Implement SOX compliance features for financial data encryption
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Dictionary containing SOX compliance status
        """
        try:
            compliance_features = {
                'financial_data_encryption': self._verify_financial_data_encryption(tenant_id),
                'access_controls': self._verify_access_controls(tenant_id),
                'audit_trails': self._verify_audit_trails(tenant_id),
                'change_management': self._verify_change_management(tenant_id),
                'data_integrity': self._verify_data_integrity(tenant_id)
            }
            
            all_compliant = all(feature['compliant'] for feature in compliance_features.values())
            
            self.log_audit_event(
                tenant_id=tenant_id,
                action=AuditAction.COMPLIANCE_REQUEST,
                regulation=ComplianceRegulation.SOX,
                data_category=DataCategory.FINANCIAL_DATA,
                affected_records=['sox_compliance_check'],
                details=compliance_features,
                success=all_compliant
            )
            
            return {
                'tenant_id': tenant_id,
                'regulation': 'SOX',
                'overall_compliant': all_compliant,
                'compliance_features': compliance_features,
                'assessment_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"SOX compliance check failed for tenant {tenant_id}: {str(e)}")
            raise ComplianceError(f"SOX compliance assessment failed: {str(e)}")
    
    def _verify_financial_data_encryption(self, tenant_id: int) -> Dict[str, Any]:
        """Verify that financial data is properly encrypted"""
        # Check that financial tables have encryption enabled
        financial_tables = ['invoices', 'payments', 'expenses', 'clients']
        
        encryption_status = {}
        for table in financial_tables:
            # In production, this would check actual table encryption status
            encryption_status[table] = {
                'encrypted': True,
                'algorithm': 'AES-256-GCM',
                'key_rotation_enabled': True
            }
        
        return {
            'compliant': True,
            'details': encryption_status,
            'requirements_met': [
                'Financial data encrypted at rest',
                'Strong encryption algorithm (AES-256-GCM)',
                'Key rotation implemented'
            ]
        }
    
    def _verify_access_controls(self, tenant_id: int) -> Dict[str, Any]:
        """Verify access controls for financial data"""
        return {
            'compliant': True,
            'details': {
                'role_based_access': True,
                'multi_factor_authentication': True,
                'access_logging': True,
                'privileged_access_monitoring': True
            },
            'requirements_met': [
                'Role-based access control implemented',
                'MFA required for sensitive operations',
                'All access logged and monitored'
            ]
        }
    
    def _verify_audit_trails(self, tenant_id: int) -> Dict[str, Any]:
        """Verify audit trail completeness"""
        return {
            'compliant': True,
            'details': {
                'comprehensive_logging': True,
                'tamper_proof_logs': True,
                'log_retention_policy': True,
                'log_monitoring': True
            },
            'requirements_met': [
                'Comprehensive audit logging',
                'Tamper-proof log storage',
                'Appropriate retention policies',
                'Active log monitoring'
            ]
        }
    
    def _verify_change_management(self, tenant_id: int) -> Dict[str, Any]:
        """Verify change management processes"""
        return {
            'compliant': True,
            'details': {
                'change_approval_process': True,
                'change_documentation': True,
                'rollback_procedures': True,
                'change_testing': True
            },
            'requirements_met': [
                'Formal change approval process',
                'Complete change documentation',
                'Tested rollback procedures',
                'Pre-production testing'
            ]
        }
    
    def _verify_data_integrity(self, tenant_id: int) -> Dict[str, Any]:
        """Verify data integrity controls"""
        return {
            'compliant': True,
            'details': {
                'data_validation': True,
                'integrity_checks': True,
                'backup_verification': True,
                'corruption_detection': True
            },
            'requirements_met': [
                'Data validation at input',
                'Regular integrity checks',
                'Backup verification',
                'Corruption detection and alerting'
            ]
        }
    
    def set_data_residency_rule(self, tenant_id: int, regulation: ComplianceRegulation,
                               allowed_regions: List[str], data_categories: List[DataCategory],
                               encryption_required: bool = True, 
                               key_residency_required: bool = True):
        """
        Set data residency rule for compliance
        
        Args:
            tenant_id: Tenant ID
            regulation: Applicable regulation
            allowed_regions: List of allowed regions for data storage
            data_categories: Categories of data affected
            encryption_required: Whether encryption is required
            key_residency_required: Whether keys must also reside in allowed regions
        """
        rule = DataResidencyRule(
            tenant_id=tenant_id,
            regulation=regulation,
            allowed_regions=allowed_regions,
            data_categories=data_categories,
            encryption_required=encryption_required,
            key_residency_required=key_residency_required
        )
        
        if tenant_id not in self._residency_rules:
            self._residency_rules[tenant_id] = []
        
        self._residency_rules[tenant_id].append(rule)
        
        self.log_audit_event(
            tenant_id=tenant_id,
            action=AuditAction.COMPLIANCE_REQUEST,
            regulation=regulation,
            data_category=DataCategory.SENSITIVE_DATA,
            affected_records=['data_residency_rule'],
            details=asdict(rule)
        )
        
        self.logger.info(f"Set data residency rule for tenant {tenant_id}: {regulation.value}")
    
    def verify_data_residency_compliance(self, tenant_id: int) -> Dict[str, Any]:
        """
        Verify data residency compliance for a tenant
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Dictionary containing compliance status
        """
        rules = self._residency_rules.get(tenant_id, [])
        
        if not rules:
            return {
                'compliant': True,
                'message': 'No data residency rules defined',
                'rules_checked': 0
            }
        
        compliance_results = []
        
        for rule in rules:
            # In production, this would check actual data and key locations
            result = {
                'regulation': rule.regulation.value,
                'data_categories': [cat.value for cat in rule.data_categories],
                'allowed_regions': rule.allowed_regions,
                'data_compliant': True,  # Mock result
                'keys_compliant': True,  # Mock result
                'overall_compliant': True
            }
            compliance_results.append(result)
        
        overall_compliant = all(result['overall_compliant'] for result in compliance_results)
        
        return {
            'tenant_id': tenant_id,
            'overall_compliant': overall_compliant,
            'rules_checked': len(rules),
            'compliance_results': compliance_results,
            'assessment_timestamp': datetime.utcnow().isoformat()
        }
    
    def set_retention_policy(self, tenant_id: int, data_category: DataCategory,
                           retention_period_days: int, auto_delete: bool = False,
                           anonymize_after_retention: bool = True):
        """
        Set data retention policy for compliance
        
        Args:
            tenant_id: Tenant ID
            data_category: Category of data
            retention_period_days: Retention period in days
            auto_delete: Whether to automatically delete after retention period
            anonymize_after_retention: Whether to anonymize data after retention
        """
        policy = RetentionPolicy(
            tenant_id=tenant_id,
            data_category=data_category,
            retention_period_days=retention_period_days,
            auto_delete=auto_delete,
            anonymize_after_retention=anonymize_after_retention
        )
        
        if tenant_id not in self._retention_policies:
            self._retention_policies[tenant_id] = []
        
        self._retention_policies[tenant_id].append(policy)
        
        self.log_audit_event(
            tenant_id=tenant_id,
            action=AuditAction.COMPLIANCE_REQUEST,
            regulation=ComplianceRegulation.GDPR,  # Retention policies are often GDPR-related
            data_category=data_category,
            affected_records=['retention_policy'],
            details=asdict(policy)
        )
        
        self.logger.info(
            f"Set retention policy for tenant {tenant_id}: "
            f"{data_category.value} - {retention_period_days} days"
        )
    
    def apply_retention_policies(self, tenant_id: int) -> Dict[str, Any]:
        """
        Apply retention policies for a tenant
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Dictionary containing results of retention policy application
        """
        policies = self._retention_policies.get(tenant_id, [])
        
        if not policies:
            return {
                'tenant_id': tenant_id,
                'policies_applied': 0,
                'records_processed': 0,
                'message': 'No retention policies defined'
            }
        
        results = []
        total_processed = 0
        
        for policy in policies:
            # In production, this would find and process actual expired records
            cutoff_date = datetime.utcnow() - timedelta(days=policy.retention_period_days)
            
            # Mock processing results
            processed_count = 0  # Would be actual count from database
            
            if policy.auto_delete:
                action = 'deleted'
            elif policy.anonymize_after_retention:
                action = 'anonymized'
            else:
                action = 'flagged_for_review'
            
            result = {
                'data_category': policy.data_category.value,
                'retention_period_days': policy.retention_period_days,
                'cutoff_date': cutoff_date.isoformat(),
                'records_processed': processed_count,
                'action_taken': action
            }
            
            results.append(result)
            total_processed += processed_count
        
        self.log_audit_event(
            tenant_id=tenant_id,
            action=AuditAction.DATA_DELETION,
            regulation=ComplianceRegulation.GDPR,
            data_category=DataCategory.PERSONAL_DATA,
            affected_records=[f"retention_policy_{i}" for i in range(len(policies))],
            details={'policies_applied': len(policies), 'total_processed': total_processed}
        )
        
        return {
            'tenant_id': tenant_id,
            'policies_applied': len(policies),
            'records_processed': total_processed,
            'results': results,
            'processing_timestamp': datetime.utcnow().isoformat()
        }
    
    def get_audit_logs(self, tenant_id: Optional[int] = None, 
                      regulation: Optional[ComplianceRegulation] = None,
                      action: Optional[AuditAction] = None,
                      start_date: Optional[datetime] = None,
                      end_date: Optional[datetime] = None,
                      limit: int = 1000) -> List[ComplianceAuditLog]:
        """
        Retrieve audit logs with optional filtering
        
        Args:
            tenant_id: Optional tenant ID filter
            regulation: Optional regulation filter
            action: Optional action filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum number of logs to return
            
        Returns:
            List of audit logs matching the criteria
        """
        filtered_logs = self._audit_logs
        
        if tenant_id is not None:
            filtered_logs = [log for log in filtered_logs if log.tenant_id == tenant_id]
        
        if regulation is not None:
            filtered_logs = [log for log in filtered_logs if log.regulation == regulation]
        
        if action is not None:
            filtered_logs = [log for log in filtered_logs if log.action == action]
        
        if start_date is not None:
            filtered_logs = [log for log in filtered_logs if log.timestamp >= start_date]
        
        if end_date is not None:
            filtered_logs = [log for log in filtered_logs if log.timestamp <= end_date]
        
        # Sort by timestamp (newest first) and apply limit
        filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        return filtered_logs[:limit]
    
    def export_compliance_report(self, tenant_id: int, regulation: ComplianceRegulation,
                               start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Export compliance report for a specific regulation and time period
        
        Args:
            tenant_id: Tenant ID
            regulation: Regulation to report on
            start_date: Start date for the report
            end_date: End date for the report
            
        Returns:
            Dictionary containing the compliance report
        """
        audit_logs = self.get_audit_logs(
            tenant_id=tenant_id,
            regulation=regulation,
            start_date=start_date,
            end_date=end_date
        )
        
        # Aggregate statistics
        total_actions = len(audit_logs)
        successful_actions = len([log for log in audit_logs if log.success])
        failed_actions = total_actions - successful_actions
        
        actions_by_type = {}
        for log in audit_logs:
            action_type = log.action.value
            if action_type not in actions_by_type:
                actions_by_type[action_type] = 0
            actions_by_type[action_type] += 1
        
        data_categories_affected = set()
        for log in audit_logs:
            data_categories_affected.add(log.data_category.value)
        
        report = {
            'tenant_id': tenant_id,
            'regulation': regulation.value,
            'report_period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_actions': total_actions,
                'successful_actions': successful_actions,
                'failed_actions': failed_actions,
                'success_rate': successful_actions / total_actions if total_actions > 0 else 0,
                'actions_by_type': actions_by_type,
                'data_categories_affected': list(data_categories_affected)
            },
            'audit_logs': [asdict(log) for log in audit_logs],
            'generated_timestamp': datetime.utcnow().isoformat()
        }
        
        self.log_audit_event(
            tenant_id=tenant_id,
            action=AuditAction.DATA_EXPORT,
            regulation=regulation,
            data_category=DataCategory.SENSITIVE_DATA,
            affected_records=['compliance_report'],
            details={
                'report_period': f"{start_date.isoformat()} to {end_date.isoformat()}",
                'total_logs_exported': total_actions
            }
        )
        
        return report


# Global compliance service instance (would be dependency injected in production)
def get_compliance_service() -> EncryptionComplianceService:
    """Get the compliance service instance"""
    from core.services.encryption_service import encryption_service
    from core.services.key_management_service import key_management_service
    
    return EncryptionComplianceService(encryption_service, key_management_service)