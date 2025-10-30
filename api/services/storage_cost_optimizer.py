"""
Storage Cost Optimization Service for Cloud File Storage.

This service implements cost optimization strategies for cloud storage including:
- Storage class selection based on file access patterns
- Lifecycle policy management for automatic tier transitions
- Cost monitoring and alerting for storage usage
- File archival and cleanup based on retention policies
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import json

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from models.models import Tenant
from models.models_per_tenant import StorageOperationLog
from services.cloud_storage.provider import StorageProvider
from storage_config.cloud_storage_config import CloudStorageConfig

logger = logging.getLogger(__name__)


class AccessPattern(Enum):
    """File access patterns for cost optimization."""
    FREQUENT = "frequent"          # Accessed multiple times per week
    INFREQUENT = "infrequent"     # Accessed less than once per week
    ARCHIVE = "archive"           # Accessed less than once per month
    COLD = "cold"                 # Accessed less than once per quarter


class StorageClass(Enum):
    """Storage classes for different cloud providers."""
    # AWS S3 Storage Classes
    S3_STANDARD = "STANDARD"
    S3_STANDARD_IA = "STANDARD_IA"
    S3_ONEZONE_IA = "ONEZONE_IA"
    S3_INTELLIGENT_TIERING = "INTELLIGENT_TIERING"
    S3_GLACIER = "GLACIER"
    S3_GLACIER_IR = "GLACIER_IR"
    S3_DEEP_ARCHIVE = "DEEP_ARCHIVE"
    
    # Azure Blob Storage Tiers
    AZURE_HOT = "Hot"
    AZURE_COOL = "Cool"
    AZURE_ARCHIVE = "Archive"
    
    # Google Cloud Storage Classes
    GCP_STANDARD = "STANDARD"
    GCP_NEARLINE = "NEARLINE"
    GCP_COLDLINE = "COLDLINE"
    GCP_ARCHIVE = "ARCHIVE"


@dataclass
class FileAccessMetrics:
    """Metrics for file access patterns."""
    file_key: str
    tenant_id: str
    total_accesses: int
    last_access_date: Optional[datetime]
    first_upload_date: datetime
    file_size: int
    content_type: str
    access_frequency_per_week: float
    days_since_last_access: int
    estimated_monthly_cost: float = 0.0
    current_storage_class: Optional[str] = None
    recommended_storage_class: Optional[str] = None
    potential_savings: float = 0.0


@dataclass
class CostOptimizationRule:
    """Rule for cost optimization based on access patterns."""
    name: str
    description: str
    access_pattern: AccessPattern
    min_file_age_days: int
    min_days_since_last_access: int
    target_storage_class: Dict[StorageProvider, StorageClass]
    estimated_cost_reduction_percent: float
    enabled: bool = True


@dataclass
class CostAlert:
    """Cost alert configuration and tracking."""
    alert_id: str
    tenant_id: str
    alert_type: str  # threshold, trend, anomaly
    threshold_amount: Optional[float] = None
    threshold_period_days: int = 30
    current_amount: float = 0.0
    triggered: bool = False
    last_triggered_at: Optional[datetime] = None
    notification_sent: bool = False


class StorageCostOptimizer:
    """
    Service for optimizing cloud storage costs through intelligent
    storage class selection and lifecycle management.
    """
    
    def __init__(self, db: Session, config: Optional[CloudStorageConfig] = None):
        """
        Initialize the storage cost optimizer.
        
        Args:
            db: Database session
            config: Cloud storage configuration
        """
        self.db = db
        self.config = config or CloudStorageConfig()
        
        # Default cost optimization rules
        self.optimization_rules = self._create_default_optimization_rules()
        
        # Cost tracking
        self.cost_alerts: Dict[str, CostAlert] = {}
        
        logger.info("Storage cost optimizer initialized")
    
    def _create_default_optimization_rules(self) -> List[CostOptimizationRule]:
        """Create default cost optimization rules."""
        return [
            CostOptimizationRule(
                name="Standard to Infrequent Access",
                description="Move files to infrequent access tier after 30 days with low access",
                access_pattern=AccessPattern.INFREQUENT,
                min_file_age_days=30,
                min_days_since_last_access=14,
                target_storage_class={
                    StorageProvider.AWS_S3: StorageClass.S3_STANDARD_IA,
                    StorageProvider.AZURE_BLOB: StorageClass.AZURE_COOL,
                    StorageProvider.GCP_STORAGE: StorageClass.GCP_NEARLINE
                },
                estimated_cost_reduction_percent=40.0
            ),
            CostOptimizationRule(
                name="Infrequent to Archive",
                description="Move files to archive tier after 90 days with minimal access",
                access_pattern=AccessPattern.ARCHIVE,
                min_file_age_days=90,
                min_days_since_last_access=60,
                target_storage_class={
                    StorageProvider.AWS_S3: StorageClass.S3_GLACIER,
                    StorageProvider.AZURE_BLOB: StorageClass.AZURE_ARCHIVE,
                    StorageProvider.GCP_STORAGE: StorageClass.GCP_COLDLINE
                },
                estimated_cost_reduction_percent=70.0
            ),
            CostOptimizationRule(
                name="Long-term Archive",
                description="Move files to deep archive after 365 days",
                access_pattern=AccessPattern.COLD,
                min_file_age_days=365,
                min_days_since_last_access=180,
                target_storage_class={
                    StorageProvider.AWS_S3: StorageClass.S3_DEEP_ARCHIVE,
                    StorageProvider.AZURE_BLOB: StorageClass.AZURE_ARCHIVE,
                    StorageProvider.GCP_STORAGE: StorageClass.GCP_ARCHIVE
                },
                estimated_cost_reduction_percent=85.0
            )
        ]
    
    def analyze_file_access_patterns(
        self,
        tenant_id: str,
        days_to_analyze: int = 90,
        min_file_age_days: int = 7
    ) -> List[FileAccessMetrics]:
        """
        Analyze file access patterns for cost optimization.
        
        Args:
            tenant_id: Tenant identifier
            days_to_analyze: Number of days to analyze for access patterns
            min_file_age_days: Minimum file age to consider for optimization
            
        Returns:
            List of file access metrics
        """
        logger.info(f"Analyzing file access patterns for tenant {tenant_id}")
        
        # Calculate date thresholds
        analysis_start_date = datetime.now() - timedelta(days=days_to_analyze)
        min_file_date = datetime.now() - timedelta(days=min_file_age_days)
        
        # Query file access data from storage operation logs
        file_metrics = {}
        
        # Get all file operations within the analysis period
        operations = self.db.query(StorageOperationLog).filter(
            and_(
                StorageOperationLog.tenant_id == tenant_id,
                StorageOperationLog.created_at >= analysis_start_date,
                StorageOperationLog.success == True
            )
        ).all()
        
        for operation in operations:
            file_key = operation.file_key
            
            if file_key not in file_metrics:
                # Initialize metrics for this file
                file_metrics[file_key] = {
                    'file_key': file_key,
                    'tenant_id': tenant_id,
                    'total_accesses': 0,
                    'download_count': 0,
                    'upload_count': 0,
                    'last_access_date': None,
                    'first_upload_date': None,
                    'file_size': operation.file_size or 0,
                    'content_type': operation.content_type or 'unknown',
                    'providers_used': set()
                }
            
            metrics = file_metrics[file_key]
            
            # Update access counts
            if operation.operation_type == 'download':
                metrics['download_count'] += 1
                metrics['total_accesses'] += 1
                
                # Update last access date
                if not metrics['last_access_date'] or operation.created_at > metrics['last_access_date']:
                    metrics['last_access_date'] = operation.created_at
            
            elif operation.operation_type == 'upload':
                metrics['upload_count'] += 1
                
                # Update first upload date
                if not metrics['first_upload_date'] or operation.created_at < metrics['first_upload_date']:
                    metrics['first_upload_date'] = operation.created_at
            
            # Track providers used
            metrics['providers_used'].add(operation.provider)
            
            # Update file size if available
            if operation.file_size and operation.file_size > metrics['file_size']:
                metrics['file_size'] = operation.file_size
        
        # Convert to FileAccessMetrics objects
        access_metrics = []
        
        for file_key, metrics in file_metrics.items():
            # Skip files that are too new
            if metrics['first_upload_date'] and metrics['first_upload_date'] > min_file_date:
                continue
            
            # Calculate access frequency
            if metrics['first_upload_date']:
                days_since_upload = (datetime.now() - metrics['first_upload_date']).days
                weeks_since_upload = max(days_since_upload / 7.0, 1.0)
                access_frequency_per_week = metrics['total_accesses'] / weeks_since_upload
            else:
                access_frequency_per_week = 0.0
            
            # Calculate days since last access
            if metrics['last_access_date']:
                days_since_last_access = (datetime.now() - metrics['last_access_date']).days
            else:
                days_since_last_access = days_to_analyze
            
            # Estimate monthly cost (simplified calculation)
            estimated_monthly_cost = self._estimate_monthly_storage_cost(
                metrics['file_size'], 
                StorageClass.S3_STANDARD  # Assume standard class for estimation
            )
            
            file_metrics_obj = FileAccessMetrics(
                file_key=file_key,
                tenant_id=tenant_id,
                total_accesses=metrics['total_accesses'],
                last_access_date=metrics['last_access_date'],
                first_upload_date=metrics['first_upload_date'] or datetime.now(),
                file_size=metrics['file_size'],
                content_type=metrics['content_type'],
                access_frequency_per_week=access_frequency_per_week,
                days_since_last_access=days_since_last_access,
                estimated_monthly_cost=estimated_monthly_cost
            )
            
            access_metrics.append(file_metrics_obj)
        
        logger.info(f"Analyzed {len(access_metrics)} files for tenant {tenant_id}")
        return access_metrics
    
    def classify_file_access_pattern(self, metrics: FileAccessMetrics) -> AccessPattern:
        """
        Classify file access pattern based on metrics.
        
        Args:
            metrics: File access metrics
            
        Returns:
            Access pattern classification
        """
        # Classify based on access frequency and recency
        if metrics.access_frequency_per_week >= 2.0:
            return AccessPattern.FREQUENT
        elif metrics.access_frequency_per_week >= 0.5 or metrics.days_since_last_access <= 7:
            return AccessPattern.INFREQUENT
        elif metrics.days_since_last_access <= 30:
            return AccessPattern.ARCHIVE
        else:
            return AccessPattern.COLD
    
    def recommend_storage_class(
        self,
        metrics: FileAccessMetrics,
        provider: StorageProvider
    ) -> Tuple[StorageClass, float]:
        """
        Recommend optimal storage class for a file.
        
        Args:
            metrics: File access metrics
            provider: Storage provider
            
        Returns:
            Tuple of (recommended_storage_class, potential_savings_percent)
        """
        access_pattern = self.classify_file_access_pattern(metrics)
        
        # Find applicable optimization rule
        for rule in self.optimization_rules:
            if not rule.enabled:
                continue
            
            if (rule.access_pattern == access_pattern and
                (datetime.now() - metrics.first_upload_date).days >= rule.min_file_age_days and
                metrics.days_since_last_access >= rule.min_days_since_last_access):
                
                if provider in rule.target_storage_class:
                    return rule.target_storage_class[provider], rule.estimated_cost_reduction_percent
        
        # Default to standard storage class
        default_classes = {
            StorageProvider.AWS_S3: StorageClass.S3_STANDARD,
            StorageProvider.AZURE_BLOB: StorageClass.AZURE_HOT,
            StorageProvider.GCP_STORAGE: StorageClass.GCP_STANDARD
        }
        
        return default_classes.get(provider, StorageClass.S3_STANDARD), 0.0
    
    def _estimate_monthly_storage_cost(
        self,
        file_size_bytes: int,
        storage_class: StorageClass
    ) -> float:
        """
        Estimate monthly storage cost for a file.
        
        Args:
            file_size_bytes: File size in bytes
            storage_class: Storage class
            
        Returns:
            Estimated monthly cost in USD
        """
        # Simplified cost calculation (AWS S3 pricing as baseline)
        # Real implementation would use actual provider pricing APIs
        
        gb_size = file_size_bytes / (1024 ** 3)  # Convert to GB
        
        # Cost per GB per month (simplified rates)
        cost_rates = {
            StorageClass.S3_STANDARD: 0.023,
            StorageClass.S3_STANDARD_IA: 0.0125,
            StorageClass.S3_ONEZONE_IA: 0.01,
            StorageClass.S3_GLACIER: 0.004,
            StorageClass.S3_DEEP_ARCHIVE: 0.00099,
            StorageClass.AZURE_HOT: 0.0208,
            StorageClass.AZURE_COOL: 0.01,
            StorageClass.AZURE_ARCHIVE: 0.00099,
            StorageClass.GCP_STANDARD: 0.020,
            StorageClass.GCP_NEARLINE: 0.010,
            StorageClass.GCP_COLDLINE: 0.004,
            StorageClass.GCP_ARCHIVE: 0.0012
        }
        
        rate = cost_rates.get(storage_class, 0.023)  # Default to S3 Standard
        return gb_size * rate
    
    def generate_cost_optimization_recommendations(
        self,
        tenant_id: str,
        provider: StorageProvider,
        days_to_analyze: int = 90
    ) -> Dict[str, Any]:
        """
        Generate cost optimization recommendations for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            provider: Storage provider to optimize for
            days_to_analyze: Number of days to analyze
            
        Returns:
            Dictionary with optimization recommendations
        """
        logger.info(f"Generating cost optimization recommendations for tenant {tenant_id}")
        
        # Analyze file access patterns
        file_metrics = self.analyze_file_access_patterns(tenant_id, days_to_analyze)
        
        recommendations = []
        total_potential_savings = 0.0
        total_current_cost = 0.0
        
        for metrics in file_metrics:
            # Get storage class recommendation
            recommended_class, savings_percent = self.recommend_storage_class(metrics, provider)
            
            # Calculate potential savings
            current_cost = metrics.estimated_monthly_cost
            potential_savings = current_cost * (savings_percent / 100.0)
            
            total_current_cost += current_cost
            total_potential_savings += potential_savings
            
            # Update metrics with recommendations
            metrics.recommended_storage_class = recommended_class.value
            metrics.potential_savings = potential_savings
            
            if potential_savings > 0:
                recommendations.append({
                    'file_key': metrics.file_key,
                    'current_storage_class': metrics.current_storage_class or 'STANDARD',
                    'recommended_storage_class': recommended_class.value,
                    'access_pattern': self.classify_file_access_pattern(metrics).value,
                    'file_size_mb': round(metrics.file_size / (1024 * 1024), 2),
                    'days_since_last_access': metrics.days_since_last_access,
                    'access_frequency_per_week': round(metrics.access_frequency_per_week, 2),
                    'current_monthly_cost': round(current_cost, 4),
                    'potential_monthly_savings': round(potential_savings, 4),
                    'savings_percent': round(savings_percent, 1)
                })
        
        # Sort recommendations by potential savings
        recommendations.sort(key=lambda x: x['potential_monthly_savings'], reverse=True)
        
        return {
            'tenant_id': tenant_id,
            'provider': provider.value,
            'analysis_period_days': days_to_analyze,
            'total_files_analyzed': len(file_metrics),
            'files_with_optimization_potential': len(recommendations),
            'total_current_monthly_cost': round(total_current_cost, 2),
            'total_potential_monthly_savings': round(total_potential_savings, 2),
            'potential_savings_percent': round(
                (total_potential_savings / total_current_cost * 100) if total_current_cost > 0 else 0, 1
            ),
            'recommendations': recommendations[:50],  # Limit to top 50 recommendations
            'generated_at': datetime.now().isoformat()
        }
    
    def create_lifecycle_policy(
        self,
        provider: StorageProvider,
        tenant_id: str,
        policy_name: str
    ) -> Dict[str, Any]:
        """
        Create lifecycle policy configuration for automatic tier transitions.
        
        Args:
            provider: Storage provider
            tenant_id: Tenant identifier
            policy_name: Name for the lifecycle policy
            
        Returns:
            Lifecycle policy configuration
        """
        logger.info(f"Creating lifecycle policy for {provider.value} - tenant {tenant_id}")
        
        if provider == StorageProvider.AWS_S3:
            return self._create_s3_lifecycle_policy(tenant_id, policy_name)
        elif provider == StorageProvider.AZURE_BLOB:
            return self._create_azure_lifecycle_policy(tenant_id, policy_name)
        elif provider == StorageProvider.GCP_STORAGE:
            return self._create_gcp_lifecycle_policy(tenant_id, policy_name)
        else:
            raise ValueError(f"Lifecycle policies not supported for provider: {provider}")
    
    def _create_s3_lifecycle_policy(self, tenant_id: str, policy_name: str) -> Dict[str, Any]:
        """Create AWS S3 lifecycle policy."""
        return {
            "Rules": [
                {
                    "ID": f"{policy_name}-standard-to-ia",
                    "Status": "Enabled",
                    "Filter": {
                        "Prefix": f"tenant_{tenant_id}/"
                    },
                    "Transitions": [
                        {
                            "Days": 30,
                            "StorageClass": "STANDARD_IA"
                        },
                        {
                            "Days": 90,
                            "StorageClass": "GLACIER"
                        },
                        {
                            "Days": 365,
                            "StorageClass": "DEEP_ARCHIVE"
                        }
                    ]
                }
            ]
        }
    
    def _create_azure_lifecycle_policy(self, tenant_id: str, policy_name: str) -> Dict[str, Any]:
        """Create Azure Blob lifecycle policy."""
        return {
            "policy": {
                "rules": [
                    {
                        "name": f"{policy_name}-tier-transitions",
                        "enabled": True,
                        "type": "Lifecycle",
                        "definition": {
                            "filters": {
                                "prefixMatch": [f"tenant_{tenant_id}/"]
                            },
                            "actions": {
                                "baseBlob": {
                                    "tierToCool": {
                                        "daysAfterModificationGreaterThan": 30
                                    },
                                    "tierToArchive": {
                                        "daysAfterModificationGreaterThan": 90
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        }
    
    def _create_gcp_lifecycle_policy(self, tenant_id: str, policy_name: str) -> Dict[str, Any]:
        """Create Google Cloud Storage lifecycle policy."""
        return {
            "lifecycle": {
                "rule": [
                    {
                        "action": {
                            "type": "SetStorageClass",
                            "storageClass": "NEARLINE"
                        },
                        "condition": {
                            "age": 30,
                            "matchesPrefix": [f"tenant_{tenant_id}/"]
                        }
                    },
                    {
                        "action": {
                            "type": "SetStorageClass",
                            "storageClass": "COLDLINE"
                        },
                        "condition": {
                            "age": 90,
                            "matchesPrefix": [f"tenant_{tenant_id}/"]
                        }
                    },
                    {
                        "action": {
                            "type": "SetStorageClass",
                            "storageClass": "ARCHIVE"
                        },
                        "condition": {
                            "age": 365,
                            "matchesPrefix": [f"tenant_{tenant_id}/"]
                        }
                    }
                ]
            }
        }   
 
    def setup_cost_alerts(
        self,
        tenant_id: str,
        monthly_threshold: float,
        growth_threshold_percent: float = 20.0
    ) -> List[CostAlert]:
        """
        Set up cost monitoring alerts for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            monthly_threshold: Monthly cost threshold in USD
            growth_threshold_percent: Alert if costs grow by this percentage
            
        Returns:
            List of created cost alerts
        """
        logger.info(f"Setting up cost alerts for tenant {tenant_id}")
        
        alerts = []
        
        # Monthly threshold alert
        threshold_alert = CostAlert(
            alert_id=f"threshold_{tenant_id}_{int(datetime.now().timestamp())}",
            tenant_id=tenant_id,
            alert_type="threshold",
            threshold_amount=monthly_threshold,
            threshold_period_days=30
        )
        alerts.append(threshold_alert)
        self.cost_alerts[threshold_alert.alert_id] = threshold_alert
        
        # Growth trend alert
        growth_alert = CostAlert(
            alert_id=f"growth_{tenant_id}_{int(datetime.now().timestamp())}",
            tenant_id=tenant_id,
            alert_type="trend",
            threshold_amount=growth_threshold_percent,
            threshold_period_days=30
        )
        alerts.append(growth_alert)
        self.cost_alerts[growth_alert.alert_id] = growth_alert
        
        logger.info(f"Created {len(alerts)} cost alerts for tenant {tenant_id}")
        return alerts
    
    def check_cost_alerts(self, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Check and trigger cost alerts for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of triggered alerts
        """
        logger.info(f"Checking cost alerts for tenant {tenant_id}")
        
        triggered_alerts = []
        current_costs = self.calculate_current_storage_costs(tenant_id)
        
        for alert in self.cost_alerts.values():
            if alert.tenant_id != tenant_id:
                continue
            
            alert_triggered = False
            alert_message = ""
            
            if alert.alert_type == "threshold":
                if current_costs['total_monthly_cost'] > alert.threshold_amount:
                    alert_triggered = True
                    alert_message = (
                        f"Monthly storage costs (${current_costs['total_monthly_cost']:.2f}) "
                        f"exceeded threshold (${alert.threshold_amount:.2f})"
                    )
            
            elif alert.alert_type == "trend":
                # Calculate cost growth over the threshold period
                previous_costs = self.calculate_historical_storage_costs(
                    tenant_id, 
                    days_back=alert.threshold_period_days * 2,
                    period_days=alert.threshold_period_days
                )
                
                if previous_costs['total_monthly_cost'] > 0:
                    growth_percent = (
                        (current_costs['total_monthly_cost'] - previous_costs['total_monthly_cost']) /
                        previous_costs['total_monthly_cost'] * 100
                    )
                    
                    if growth_percent > alert.threshold_amount:
                        alert_triggered = True
                        alert_message = (
                            f"Storage costs grew by {growth_percent:.1f}% "
                            f"(threshold: {alert.threshold_amount:.1f}%)"
                        )
            
            if alert_triggered and not alert.triggered:
                alert.triggered = True
                alert.current_amount = current_costs['total_monthly_cost']
                alert.last_triggered_at = datetime.now()
                
                triggered_alert = {
                    'alert_id': alert.alert_id,
                    'tenant_id': tenant_id,
                    'alert_type': alert.alert_type,
                    'message': alert_message,
                    'current_amount': alert.current_amount,
                    'threshold_amount': alert.threshold_amount,
                    'triggered_at': alert.last_triggered_at.isoformat(),
                    'recommendations': self._generate_cost_reduction_recommendations(tenant_id)
                }
                
                triggered_alerts.append(triggered_alert)
                logger.warning(f"Cost alert triggered for tenant {tenant_id}: {alert_message}")
        
        return triggered_alerts
    
    def calculate_current_storage_costs(self, tenant_id: str) -> Dict[str, Any]:
        """
        Calculate current storage costs for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with current cost breakdown
        """
        logger.info(f"Calculating current storage costs for tenant {tenant_id}")
        
        # Get file metrics for cost calculation
        file_metrics = self.analyze_file_access_patterns(tenant_id, days_to_analyze=30)
        
        costs_by_provider = {}
        costs_by_file_type = {}
        total_cost = 0.0
        total_storage_gb = 0.0
        
        for metrics in file_metrics:
            # Estimate current storage class (simplified)
            access_pattern = self.classify_file_access_pattern(metrics)
            
            # Determine likely current storage class based on access pattern
            if access_pattern == AccessPattern.FREQUENT:
                current_class = StorageClass.S3_STANDARD
            elif access_pattern == AccessPattern.INFREQUENT:
                current_class = StorageClass.S3_STANDARD_IA
            elif access_pattern == AccessPattern.ARCHIVE:
                current_class = StorageClass.S3_GLACIER
            else:
                current_class = StorageClass.S3_DEEP_ARCHIVE
            
            # Calculate cost
            file_cost = self._estimate_monthly_storage_cost(metrics.file_size, current_class)
            file_size_gb = metrics.file_size / (1024 ** 3)
            
            total_cost += file_cost
            total_storage_gb += file_size_gb
            
            # Track by provider (simplified - assume primary provider)
            provider = self.config.get_primary_provider().value
            if provider not in costs_by_provider:
                costs_by_provider[provider] = {'cost': 0.0, 'storage_gb': 0.0, 'file_count': 0}
            
            costs_by_provider[provider]['cost'] += file_cost
            costs_by_provider[provider]['storage_gb'] += file_size_gb
            costs_by_provider[provider]['file_count'] += 1
            
            # Track by file type
            file_type = metrics.content_type.split('/')[0] if '/' in metrics.content_type else 'other'
            if file_type not in costs_by_file_type:
                costs_by_file_type[file_type] = {'cost': 0.0, 'storage_gb': 0.0, 'file_count': 0}
            
            costs_by_file_type[file_type]['cost'] += file_cost
            costs_by_file_type[file_type]['storage_gb'] += file_size_gb
            costs_by_file_type[file_type]['file_count'] += 1
        
        return {
            'tenant_id': tenant_id,
            'total_monthly_cost': round(total_cost, 2),
            'total_storage_gb': round(total_storage_gb, 2),
            'total_file_count': len(file_metrics),
            'cost_per_gb': round(total_cost / total_storage_gb, 4) if total_storage_gb > 0 else 0,
            'costs_by_provider': costs_by_provider,
            'costs_by_file_type': costs_by_file_type,
            'calculated_at': datetime.now().isoformat()
        }
    
    def calculate_historical_storage_costs(
        self,
        tenant_id: str,
        days_back: int = 30,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Calculate historical storage costs for comparison.
        
        Args:
            tenant_id: Tenant identifier
            days_back: How many days back to start the calculation
            period_days: Period length for calculation
            
        Returns:
            Dictionary with historical cost data
        """
        logger.info(f"Calculating historical storage costs for tenant {tenant_id}")
        
        # Calculate date range
        end_date = datetime.now() - timedelta(days=days_back)
        start_date = end_date - timedelta(days=period_days)
        
        # Query historical operations
        operations = self.db.query(StorageOperationLog).filter(
            and_(
                StorageOperationLog.tenant_id == tenant_id,
                StorageOperationLog.created_at >= start_date,
                StorageOperationLog.created_at <= end_date,
                StorageOperationLog.operation_type == 'upload',
                StorageOperationLog.success == True
            )
        ).all()
        
        total_cost = 0.0
        total_storage_gb = 0.0
        file_count = 0
        
        for operation in operations:
            if operation.file_size:
                # Estimate cost using standard storage class
                file_cost = self._estimate_monthly_storage_cost(
                    operation.file_size, 
                    StorageClass.S3_STANDARD
                )
                file_size_gb = operation.file_size / (1024 ** 3)
                
                total_cost += file_cost
                total_storage_gb += file_size_gb
                file_count += 1
        
        return {
            'tenant_id': tenant_id,
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'total_monthly_cost': round(total_cost, 2),
            'total_storage_gb': round(total_storage_gb, 2),
            'total_file_count': file_count,
            'cost_per_gb': round(total_cost / total_storage_gb, 4) if total_storage_gb > 0 else 0
        }
    
    def _generate_cost_reduction_recommendations(self, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Generate cost reduction recommendations for alerts.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of cost reduction recommendations
        """
        recommendations = []
        
        # Get optimization recommendations
        provider = StorageProvider(self.config.PRIMARY_PROVIDER)
        optimization_data = self.generate_cost_optimization_recommendations(tenant_id, provider)
        
        if optimization_data['total_potential_monthly_savings'] > 0:
            recommendations.append({
                'type': 'storage_class_optimization',
                'description': 'Optimize storage classes based on access patterns',
                'potential_monthly_savings': optimization_data['total_potential_monthly_savings'],
                'files_affected': optimization_data['files_with_optimization_potential'],
                'action': 'Review and apply storage class recommendations'
            })
        
        # Check for large files that could be compressed
        file_metrics = self.analyze_file_access_patterns(tenant_id)
        large_files = [m for m in file_metrics if m.file_size > 100 * 1024 * 1024]  # > 100MB
        
        if large_files:
            total_large_file_cost = sum(m.estimated_monthly_cost for m in large_files)
            recommendations.append({
                'type': 'file_compression',
                'description': 'Consider compressing large files',
                'potential_monthly_savings': round(total_large_file_cost * 0.3, 2),  # Assume 30% compression
                'files_affected': len(large_files),
                'action': 'Implement file compression for large files'
            })
        
        # Check for old files that could be deleted
        old_files = [m for m in file_metrics if m.days_since_last_access > 365]
        
        if old_files:
            total_old_file_cost = sum(m.estimated_monthly_cost for m in old_files)
            recommendations.append({
                'type': 'file_cleanup',
                'description': 'Delete files not accessed in over a year',
                'potential_monthly_savings': round(total_old_file_cost, 2),
                'files_affected': len(old_files),
                'action': 'Review and delete unused files'
            })
        
        return recommendations
    
    def generate_cost_report(
        self,
        tenant_id: str,
        report_period_days: int = 30,
        include_projections: bool = True
    ) -> Dict[str, Any]:
        """
        Generate comprehensive cost report for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            report_period_days: Period for the report in days
            include_projections: Whether to include cost projections
            
        Returns:
            Comprehensive cost report
        """
        logger.info(f"Generating cost report for tenant {tenant_id}")
        
        # Get current costs
        current_costs = self.calculate_current_storage_costs(tenant_id)
        
        # Get historical costs for comparison
        historical_costs = self.calculate_historical_storage_costs(
            tenant_id, 
            days_back=report_period_days,
            period_days=report_period_days
        )
        
        # Calculate cost trends
        cost_trend = 0.0
        if historical_costs['total_monthly_cost'] > 0:
            cost_trend = (
                (current_costs['total_monthly_cost'] - historical_costs['total_monthly_cost']) /
                historical_costs['total_monthly_cost'] * 100
            )
        
        # Get optimization recommendations
        provider = StorageProvider(self.config.PRIMARY_PROVIDER)
        optimization_data = self.generate_cost_optimization_recommendations(tenant_id, provider)
        
        # Calculate projections if requested
        projections = {}
        if include_projections:
            # Simple linear projection based on current trend
            monthly_growth_rate = cost_trend / 100.0
            
            projections = {
                'next_month': round(current_costs['total_monthly_cost'] * (1 + monthly_growth_rate), 2),
                'next_quarter': round(current_costs['total_monthly_cost'] * (1 + monthly_growth_rate * 3), 2),
                'next_year': round(current_costs['total_monthly_cost'] * (1 + monthly_growth_rate * 12), 2),
                'with_optimization': round(
                    current_costs['total_monthly_cost'] - optimization_data['total_potential_monthly_savings'], 2
                )
            }
        
        # Get storage usage trends
        usage_trends = self._calculate_storage_usage_trends(tenant_id, report_period_days)
        
        report = {
            'tenant_id': tenant_id,
            'report_period_days': report_period_days,
            'generated_at': datetime.now().isoformat(),
            
            # Current costs
            'current_costs': current_costs,
            
            # Historical comparison
            'historical_costs': historical_costs,
            'cost_trend_percent': round(cost_trend, 1),
            
            # Usage trends
            'usage_trends': usage_trends,
            
            # Optimization opportunities
            'optimization_summary': {
                'total_potential_savings': optimization_data['total_potential_monthly_savings'],
                'files_with_optimization_potential': optimization_data['files_with_optimization_potential'],
                'potential_savings_percent': optimization_data['potential_savings_percent']
            },
            
            # Top recommendations
            'top_recommendations': optimization_data['recommendations'][:10],
            
            # Cost projections
            'projections': projections,
            
            # Alerts status
            'active_alerts': len([a for a in self.cost_alerts.values() 
                                if a.tenant_id == tenant_id and a.triggered]),
            
            # Summary insights
            'insights': self._generate_cost_insights(current_costs, historical_costs, optimization_data)
        }
        
        return report
    
    def _calculate_storage_usage_trends(self, tenant_id: str, days: int) -> Dict[str, Any]:
        """Calculate storage usage trends over time."""
        
        # Query upload operations over the period
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        uploads = self.db.query(StorageOperationLog).filter(
            and_(
                StorageOperationLog.tenant_id == tenant_id,
                StorageOperationLog.operation_type == 'upload',
                StorageOperationLog.success == True,
                StorageOperationLog.created_at >= start_date
            )
        ).all()
        
        # Group by week
        weekly_data = {}
        for upload in uploads:
            week_start = upload.created_at.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = week_start - timedelta(days=week_start.weekday())
            week_key = week_start.strftime('%Y-%m-%d')
            
            if week_key not in weekly_data:
                weekly_data[week_key] = {'uploads': 0, 'total_size': 0, 'total_cost': 0.0}
            
            weekly_data[week_key]['uploads'] += 1
            if upload.file_size:
                weekly_data[week_key]['total_size'] += upload.file_size
                weekly_data[week_key]['total_cost'] += self._estimate_monthly_storage_cost(
                    upload.file_size, StorageClass.S3_STANDARD
                )
        
        return {
            'period_days': days,
            'total_uploads': len(uploads),
            'total_size_gb': round(sum(u.file_size or 0 for u in uploads) / (1024**3), 2),
            'weekly_breakdown': weekly_data,
            'average_weekly_uploads': round(len(uploads) / max(days / 7, 1), 1),
            'upload_trend': 'increasing' if len(uploads) > 0 else 'stable'  # Simplified
        }
    
    def _generate_cost_insights(
        self,
        current_costs: Dict[str, Any],
        historical_costs: Dict[str, Any],
        optimization_data: Dict[str, Any]
    ) -> List[str]:
        """Generate insights from cost analysis."""
        
        insights = []
        
        # Cost trend insights
        if historical_costs['total_monthly_cost'] > 0:
            growth = ((current_costs['total_monthly_cost'] - historical_costs['total_monthly_cost']) /
                     historical_costs['total_monthly_cost'] * 100)
            
            if growth > 20:
                insights.append(f"Storage costs have increased by {growth:.1f}% - consider optimization")
            elif growth < -10:
                insights.append(f"Storage costs have decreased by {abs(growth):.1f}% - good cost management")
            else:
                insights.append("Storage costs are relatively stable")
        
        # Optimization insights
        if optimization_data['potential_savings_percent'] > 30:
            insights.append(f"Significant cost savings available ({optimization_data['potential_savings_percent']:.1f}%)")
        elif optimization_data['potential_savings_percent'] > 10:
            insights.append(f"Moderate cost savings available ({optimization_data['potential_savings_percent']:.1f}%)")
        
        # Storage efficiency insights
        if current_costs['cost_per_gb'] > 0.05:  # Above $0.05/GB
            insights.append("Storage costs per GB are high - consider storage class optimization")
        
        # File type insights
        if 'costs_by_file_type' in current_costs:
            file_types = current_costs['costs_by_file_type']
            if file_types:
                most_expensive_type = max(file_types.items(), key=lambda x: x[1]['cost'])
                insights.append(f"'{most_expensive_type[0]}' files account for the highest storage costs")
        
        return insights
    
    def get_tenant_cost_summary(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get a quick cost summary for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Quick cost summary
        """
        current_costs = self.calculate_current_storage_costs(tenant_id)
        
        # Check for active alerts
        active_alerts = [a for a in self.cost_alerts.values() 
                        if a.tenant_id == tenant_id and a.triggered]
        
        # Get quick optimization estimate
        provider = StorageProvider(self.config.PRIMARY_PROVIDER)
        optimization_data = self.generate_cost_optimization_recommendations(tenant_id, provider)
        
        return {
            'tenant_id': tenant_id,
            'monthly_cost': current_costs['total_monthly_cost'],
            'storage_gb': current_costs['total_storage_gb'],
            'file_count': current_costs['total_file_count'],
            'potential_savings': optimization_data['total_potential_monthly_savings'],
            'active_alerts': len(active_alerts),
            'optimization_opportunities': optimization_data['files_with_optimization_potential'],
            'last_updated': datetime.now().isoformat()
        }
