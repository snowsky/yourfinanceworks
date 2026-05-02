"""
Feature Configuration Service

This service provides centralized configuration for all licensable features
in the system. It defines feature metadata and provides methods to check
feature availability with environment variable fallback support.
"""

import os
from typing import Optional, Dict, List
from functools import lru_cache
from sqlalchemy.orm import Session

from core.services.license_service import LicenseService


class FeatureConfigService:
    """Centralized service for feature availability checks and configuration"""
    
    # Feature definitions with metadata
    FEATURES = {
        # AI Features
        'ai_invoice': {
            'name': 'AI Invoice Processing',
            'description': 'AI-powered invoice data extraction and processing',
            'category': 'ai',
            'env_var': 'FEATURE_AI_INVOICE_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'ai_expense': {
            'name': 'AI Expense Processing',
            'description': 'AI-powered expense OCR and categorization',
            'category': 'ai',
            'env_var': 'FEATURE_AI_EXPENSE_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'ai_bank_statement': {
            'name': 'AI Bank Statement Processing',
            'description': 'AI-powered bank statement parsing and transaction extraction',
            'category': 'ai',
            'env_var': 'FEATURE_AI_BANK_STATEMENT_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'ai_chat': {
            'name': 'AI Chat Assistant',
            'description': 'Conversational AI assistant for invoice and expense queries',
            'category': 'ai',
            'env_var': 'FEATURE_AI_CHAT_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        
        # Integration Features
        # 'tax_integration': {
        #     'name': 'Tax Service Integration',
        #     'description': 'Automated tax tracking and reporting integration',
        #     'category': 'integration',
        #     'env_var': 'FEATURE_TAX_INTEGRATION_ENABLED',
        #     'default': False,
        #     'license_tier': 'commercial'
        # },
        'slack_integration': {
            'name': 'Slack Integration',
            'description': 'Slack bot commands and notifications',
            'category': 'integration',
            'env_var': 'FEATURE_SLACK_INTEGRATION_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'cloud_storage': {
            'name': 'Cloud Storage Provider Management',
            'description': 'Configure and monitor AWS S3, Azure Blob, and GCP Storage providers',
            'category': 'integration',
            'env_var': 'FEATURE_CLOUD_STORAGE_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'sso': {
            'name': 'SSO Authentication',
            'description': 'Google and Azure AD single sign-on',
            'category': 'integration',
            'env_var': 'FEATURE_SSO_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'mfa_chain': {
            'name': 'MFA Chain Authentication',
            'description': 'Multi-step authenticator chain after password or SSO sign-in',
            'category': 'integration',
            'env_var': 'FEATURE_MFA_CHAIN_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'email_integration': {
            'name': 'Email Integration',
            'description': 'Ingest expenses from email via IMAP',
            'category': 'integration',
            'env_var': 'FEATURE_EMAIL_INTEGRATION_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'workflow_automation': {
            'name': 'Workflow Automation',
            'description': 'Automate finance follow-ups with predefined triggers and actions',
            'category': 'integration',
            'env_var': 'FEATURE_WORKFLOW_AUTOMATION_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'external_api': {
            'name': 'External API Access',
            'description': 'External API access with API key authentication for all financial domains (expenses, invoices, statements, portfolio)',
            'category': 'integration',
            'env_var': 'FEATURE_EXTERNAL_API_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'external_transactions': {
            'name': 'External Transactions',
            'description': 'Ingest transaction data via external API',
            'category': 'integration',
            'env_var': 'FEATURE_EXTERNAL_TRANSACTIONS_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        
        # Advanced Features
        'advanced_export': {
            'name': 'Advanced Export',
            'description': 'Export data to cloud storage destinations',
            'category': 'advanced',
            'env_var': 'FEATURE_ADVANCED_EXPORT_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'batch_processing': {
            'name': 'Batch Processing',
            'description': 'Bulk file uploads and batch processing',
            'category': 'advanced',
            'env_var': 'FEATURE_BATCH_PROCESSING_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'approvals': {
            'name': 'Approval Workflows',
            'description': 'Multi-level expense and invoice approval workflows',
            'category': 'advanced',
            'env_var': 'FEATURE_APPROVALS_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'reporting': {
            'name': 'Advanced Reporting',
            'description': 'Custom reports and analytics dashboards',
            'category': 'advanced',
            'env_var': 'FEATURE_REPORTING_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'cash_flow': {
            'name': 'Cash Flow Forecasting',
            'description': 'Cash flow forecasts, runway analysis, and scenario planning',
            'category': 'advanced',
            'env_var': 'FEATURE_CASH_FLOW_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'approval_analytics': {
            'name': 'Approval Analytics',
            'description': 'Advanced analytics and reporting for approval workflows',
            'category': 'advanced',
            'env_var': 'FEATURE_APPROVAL_ANALYTICS_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'advanced_search': {
            'name': 'Advanced Search',
            'description': 'Full-text search across all entities',
            'category': 'advanced',
            'env_var': 'FEATURE_ADVANCED_SEARCH_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'prompt_management': {
            'name': 'Prompt Management',
            'description': 'AI prompt template management and customization',
            'category': 'advanced',
            'env_var': 'FEATURE_PROMPT_MANAGEMENT_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'anomaly_detection': {
            'name': 'FinanceWorks Insights',
            'description': 'Intelligent financial oversight and transaction integrity monitoring',
            'category': 'advanced',
            'env_var': 'FEATURE_ANOMALY_DETECTION_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
        'plugin_management': {
            'name': 'Plugin Management',
            'description': 'Enable/disable plugins through settings interface with dynamic sidebar integration',
            'category': 'advanced',
            'env_var': 'FEATURE_PLUGIN_MANAGEMENT_ENABLED',
            'default': False,
            'license_tier': 'commercial'
        },
    }
    
    @classmethod
    def is_enabled(
        cls,
        feature_id: str,
        db: Optional[Session] = None,
        check_license: bool = True
    ) -> bool:
        """
        Check if a feature is enabled.
        
        Priority order:
        1. License check (if check_license=True and db provided)
        2. Environment variable
        3. Default value
        
        Args:
            feature_id: Feature ID to check (e.g., "ai_invoice")
            db: Database session for license checks (optional)
            check_license: Whether to check license status (default: True)
            
        Returns:
            True if feature is enabled, False otherwise
        """
        if feature_id not in cls.FEATURES:
            return False
        
        feature = cls.FEATURES[feature_id]
        tier = feature.get('license_tier', 'commercial')
        
        # Check license if database session provided and check_license is True
        if check_license and db is not None:
            try:
                license_service = LicenseService(db)
                # If license check passes, feature is enabled
                if license_service.has_feature(feature_id, tier=tier):
                    return True
                
                # Check if license status is invalid (fresh install)
                license_status = license_service.get_license_status()
                if license_status.get("license_status") == "invalid":
                    # For commercial features, require license selection first
                    # Only core features can fall through to env vars/defaults
                    if tier == "commercial":
                        return False
                    # Core features can use env vars/defaults on fresh install
                    # Fall through to env var check
                else:
                    # If license check fails but we're in trial/grace period, check env var
                    trial_status = license_service.get_trial_status()
                    if not (trial_status["trial_active"] or trial_status["in_grace_period"]):
                        # Not in trial/grace and feature not licensed
                        return False
            except Exception:
                # If license check fails, fall through to env var check
                pass
        
        # Check environment variable
        env_var = feature.get('env_var')
        if env_var:
            env_value = os.getenv(env_var)
            if env_value is not None:
                return env_value.lower() in ('true', '1', 'yes', 'on')
        
        # Return default value
        return feature.get('default', False)
    
    @classmethod
    def get_enabled_features(
        cls,
        db: Optional[Session] = None,
        check_license: bool = True
    ) -> Dict[str, bool]:
        """
        Get all features and their enabled status.
        
        Args:
            db: Database session for license checks (optional)
            check_license: Whether to check license status (default: True)
            
        Returns:
            Dictionary mapping feature IDs to their enabled status
        """
        return {
            feature_id: cls.is_enabled(feature_id, db, check_license)
            for feature_id in cls.FEATURES.keys()
        }
    
    @classmethod
    def get_feature_info(cls, feature_id: str) -> Optional[Dict]:
        """
        Get metadata for a specific feature.
        
        Args:
            feature_id: Feature ID to get info for
            
        Returns:
            Dictionary with feature metadata or None if not found
        """
        if feature_id not in cls.FEATURES:
            return None
        
        feature = cls.FEATURES[feature_id].copy()
        # Remove internal fields
        feature.pop('env_var', None)
        feature.pop('default', None)
        return feature
    
    @classmethod
    def get_all_features(cls) -> List[Dict]:
        """
        Get list of all available features with metadata.
        
        Returns:
            List of dictionaries containing feature information
        """
        features = []
        for feature_id, feature_data in cls.FEATURES.items():
            features.append({
                'id': feature_id,
                'name': feature_data['name'],
                'description': feature_data['description'],
                'category': feature_data['category']
            })
        return features
    
    @classmethod
    def get_features_by_category(cls, category: str) -> List[Dict]:
        """
        Get all features in a specific category.
        
        Args:
            category: Category to filter by ('ai', 'integration', 'advanced')
            
        Returns:
            List of features in the specified category
        """
        features = []
        for feature_id, feature_data in cls.FEATURES.items():
            if feature_data['category'] == category:
                features.append({
                    'id': feature_id,
                    'name': feature_data['name'],
                    'description': feature_data['description'],
                    'category': feature_data['category']
                })
        return features
    
    @classmethod
    def get_categories(cls) -> List[str]:
        """
        Get list of all feature categories.
        
        Returns:
            List of unique category names
        """
        categories = set()
        for feature_data in cls.FEATURES.values():
            categories.add(feature_data['category'])
        return sorted(list(categories))
