"""
Encryption Security Integration Service

This service integrates monitoring, compliance, and alerting services to provide
a comprehensive security management system for encryption operations.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from contextlib import contextmanager

from core.services.encryption_monitoring_service import EncryptionMonitoringService, monitoring_service
from core.services.encryption_compliance_service import EncryptionComplianceService, get_compliance_service
from core.services.encryption_alerting_service import EncryptionAlertingService, get_alerting_service
from core.services.encryption_alerting_service import AlertType, AlertSeverity
from core.services.encryption_compliance_service import AuditAction, ComplianceRegulation, DataCategory
from core.exceptions.encryption_exceptions import SecurityIntegrationError


class EncryptionSecurityIntegration:
    """
    Integration service that coordinates monitoring, compliance, and alerting
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize services
        self.monitoring_service = monitoring_service
        self.compliance_service = get_compliance_service()
        self.alerting_service = get_alerting_service()
        
        # Set up integration hooks
        self._setup_monitoring_alerts()
        
        self.logger.info("Encryption security integration service initialized")
    
    def _setup_monitoring_alerts(self):
        """Set up automatic alerting based on monitoring metrics"""
        # This would be implemented with callbacks or event listeners
        # For now, we'll provide methods to check and trigger alerts
        pass
    
    @contextmanager
    def monitor_with_compliance(self, operation_type: str, tenant_id: int,
                               regulation: ComplianceRegulation,
                               data_category: DataCategory,
                               affected_records: List[str],
                               user_id: Optional[int] = None,
                               ip_address: Optional[str] = None):
        """
        Context manager that combines monitoring and compliance logging
        
        Args:
            operation_type: Type of operation
            tenant_id: Tenant ID
            regulation: Applicable regulation
            data_category: Category of data
            affected_records: Records being affected
            user_id: User performing the operation
            ip_address: IP address of the request
        """
        # Start monitoring
        with self.monitoring_service.monitor_operation(operation_type, tenant_id) as monitor:
            try:
                yield monitor
                
                # Log successful compliance event
                self.compliance_service.log_audit_event(
                    tenant_id=tenant_id,
                    action=self._map_operation_to_audit_action(operation_type),
                    regulation=regulation,
                    data_category=data_category,
                    affected_records=affected_records,
                    details={'operation_type': operation_type},
                    user_id=user_id,
                    ip_address=ip_address,
                    success=True
                )
                
            except Exception as e:
                # Log failed compliance event
                self.compliance_service.log_audit_event(
                    tenant_id=tenant_id,
                    action=self._map_operation_to_audit_action(operation_type),
                    regulation=regulation,
                    data_category=data_category,
                    affected_records=affected_records,
                    details={'operation_type': operation_type, 'error': str(e)},
                    user_id=user_id,
                    ip_address=ip_address,
                    success=False,
                    error_message=str(e)
                )
                
                # Trigger security alert
                self.alerting_service.trigger_alert(
                    alert_type=self._map_operation_to_alert_type(operation_type),
                    severity=AlertSeverity.HIGH,
                    title=f"Encryption Operation Failed: {operation_type}",
                    description=f"Failed {operation_type} operation for tenant {tenant_id}: {str(e)}",
                    tenant_id=tenant_id,
                    affected_systems=[operation_type],
                    details={
                        'operation_type': operation_type,
                        'error': str(e),
                        'regulation': regulation.value,
                        'data_category': data_category.value
                    }
                )
                
                raise
    
    def _map_operation_to_audit_action(self, operation_type: str) -> AuditAction:
        """Map operation type to audit action"""
        mapping = {
            'encrypt': AuditAction.DATA_MODIFICATION,
            'decrypt': AuditAction.DATA_ACCESS,
            'key_access': AuditAction.KEY_ACCESS,
            'key_rotation': AuditAction.KEY_ROTATION
        }
        return mapping.get(operation_type, AuditAction.DATA_ACCESS)
    
    def _map_operation_to_alert_type(self, operation_type: str) -> AlertType:
        """Map operation type to alert type"""
        mapping = {
            'encrypt': AlertType.ENCRYPTION_FAILURE,
            'decrypt': AlertType.DECRYPTION_FAILURE,
            'key_access': AlertType.KEY_ACCESS_FAILURE,
            'key_rotation': AlertType.KEY_ROTATION_FAILURE
        }
        return mapping.get(operation_type, AlertType.SECURITY_INCIDENT)
    
    def check_and_trigger_alerts(self):
        """Check monitoring metrics and trigger alerts if thresholds are exceeded"""
        try:
            # Get current performance stats
            stats = self.monitoring_service.get_performance_stats(time_window_hours=1)
            
            for operation_type, stat in stats.items():
                # Check error rate
                if stat.error_rate > 0.05:  # 5% threshold
                    self.alerting_service.trigger_alert(
                        alert_type=AlertType.HIGH_ERROR_RATE,
                        severity=AlertSeverity.HIGH,
                        title=f"High Error Rate: {operation_type}",
                        description=f"Error rate for {operation_type} operations is {stat.error_rate:.2%}",
                        affected_systems=[operation_type],
                        details={
                            'operation_type': operation_type,
                            'error_rate': stat.error_rate,
                            'total_operations': stat.total_operations,
                            'failed_operations': stat.failed_operations
                        }
                    )
                
                # Check performance degradation
                if stat.avg_duration_ms > 1000:  # 1 second threshold
                    self.alerting_service.trigger_alert(
                        alert_type=AlertType.PERFORMANCE_DEGRADATION,
                        severity=AlertSeverity.MEDIUM,
                        title=f"Performance Degradation: {operation_type}",
                        description=f"Average duration for {operation_type} is {stat.avg_duration_ms:.2f}ms",
                        affected_systems=[operation_type],
                        details={
                            'operation_type': operation_type,
                            'avg_duration_ms': stat.avg_duration_ms,
                            'p95_duration_ms': stat.p95_duration_ms,
                            'p99_duration_ms': stat.p99_duration_ms
                        }
                    )
            
            # Check for suspicious activities
            suspicious_activities = self.monitoring_service.get_suspicious_activities(hours_back=1)
            for activity in suspicious_activities:
                self.alerting_service.trigger_alert(
                    alert_type=AlertType.SUSPICIOUS_ACTIVITY,
                    severity=AlertSeverity.HIGH,
                    title=f"Suspicious Activity: {activity['activity_type']}",
                    description=f"Suspicious encryption activity detected for tenant {activity['tenant_id']}",
                    tenant_id=activity['tenant_id'],
                    affected_systems=['encryption_service'],
                    details=activity
                )
            
        except Exception as e:
            self.logger.error(f"Error checking alerts: {str(e)}")
    
    def generate_security_dashboard(self, tenant_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate a comprehensive security dashboard
        
        Args:
            tenant_id: Optional tenant ID to filter data
            
        Returns:
            Dictionary containing dashboard data
        """
        try:
            # Get monitoring data
            health_status = self.monitoring_service.get_health_status()
            performance_stats = self.monitoring_service.get_performance_stats(time_window_hours=24)
            key_access_patterns = self.monitoring_service.get_key_access_patterns(tenant_id)
            
            # Get compliance data
            audit_logs = self.compliance_service.get_audit_logs(
                tenant_id=tenant_id,
                start_date=datetime.utcnow() - timedelta(hours=24),
                limit=100
            )
            
            # Get alerting data
            alerts = self.alerting_service.get_alerts(
                tenant_id=tenant_id,
                resolved=False,
                limit=50
            )
            alert_stats = self.alerting_service.get_alert_statistics(hours_back=24)
            
            dashboard = {
                'timestamp': datetime.utcnow().isoformat(),
                'tenant_id': tenant_id,
                'health_status': health_status,
                'performance_stats': {op: {
                    'total_operations': stat.total_operations,
                    'error_rate': stat.error_rate,
                    'avg_duration_ms': stat.avg_duration_ms,
                    'operations_per_second': stat.operations_per_second
                } for op, stat in performance_stats.items()},
                'key_access_summary': {
                    'total_patterns': len(key_access_patterns),
                    'unusual_access_detected': len([p for p in key_access_patterns if p.unusual_access_detected])
                },
                'compliance_summary': {
                    'total_audit_logs_24h': len(audit_logs),
                    'successful_operations': len([log for log in audit_logs if log.success]),
                    'failed_operations': len([log for log in audit_logs if not log.success])
                },
                'alert_summary': {
                    'active_alerts': len(alerts),
                    'critical_alerts': len([a for a in alerts if a.severity == AlertSeverity.CRITICAL]),
                    'high_alerts': len([a for a in alerts if a.severity == AlertSeverity.HIGH]),
                    'alert_stats_24h': alert_stats
                },
                'security_score': self._calculate_security_score(
                    health_status, performance_stats, alerts, audit_logs
                )
            }
            
            return dashboard
            
        except Exception as e:
            self.logger.error(f"Error generating security dashboard: {str(e)}")
            raise SecurityIntegrationError(f"Failed to generate security dashboard: {str(e)}")
    
    def _calculate_security_score(self, health_status: Dict[str, Any],
                                performance_stats: Dict[str, Any],
                                alerts: List[Any],
                                audit_logs: List[Any]) -> Dict[str, Any]:
        """Calculate an overall security score"""
        score = 100  # Start with perfect score
        
        # Deduct points for health issues
        if health_status['status'] == 'degraded':
            score -= 20
        elif health_status['status'] == 'warning':
            score -= 10
        
        # Deduct points for high error rates
        for stat in performance_stats.values():
            if hasattr(stat, 'error_rate') and stat.error_rate > 0.05:
                score -= 15
        
        # Deduct points for active alerts
        critical_alerts = len([a for a in alerts if hasattr(a, 'severity') and a.severity == AlertSeverity.CRITICAL])
        high_alerts = len([a for a in alerts if hasattr(a, 'severity') and a.severity == AlertSeverity.HIGH])
        
        score -= critical_alerts * 25
        score -= high_alerts * 10
        
        # Deduct points for failed operations
        failed_operations = len([log for log in audit_logs if not log.success])
        if failed_operations > 0:
            score -= min(failed_operations * 2, 20)  # Cap at 20 points
        
        score = max(0, score)  # Don't go below 0
        
        # Determine security level
        if score >= 90:
            level = "excellent"
        elif score >= 75:
            level = "good"
        elif score >= 60:
            level = "fair"
        elif score >= 40:
            level = "poor"
        else:
            level = "critical"
        
        return {
            'score': score,
            'level': level,
            'factors': {
                'health_status': health_status['status'],
                'active_critical_alerts': critical_alerts,
                'active_high_alerts': high_alerts,
                'failed_operations_24h': failed_operations
            }
        }
    
    def handle_gdpr_request_with_monitoring(self, tenant_id: int, user_email: str,
                                          request_details: Dict[str, Any],
                                          user_id: Optional[int] = None,
                                          ip_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle GDPR request with full monitoring and alerting
        
        Args:
            tenant_id: Tenant ID
            user_email: Email of the user
            request_details: Request details
            user_id: User making the request
            ip_address: IP address
            
        Returns:
            Result of the GDPR request processing
        """
        with self.monitor_with_compliance(
            operation_type='gdpr_deletion',
            tenant_id=tenant_id,
            regulation=ComplianceRegulation.GDPR,
            data_category=DataCategory.PERSONAL_DATA,
            affected_records=[user_email],
            user_id=user_id,
            ip_address=ip_address
        ):
            result = self.compliance_service.handle_gdpr_right_to_be_forgotten(
                tenant_id, user_email, request_details
            )
            
            # Trigger success alert
            self.alerting_service.trigger_alert(
                alert_type=AlertType.COMPLIANCE_VIOLATION,  # Using as compliance action
                severity=AlertSeverity.LOW,
                title="GDPR Right-to-be-Forgotten Completed",
                description=f"Successfully processed GDPR deletion request for {user_email}",
                tenant_id=tenant_id,
                affected_systems=['compliance_service'],
                details={
                    'user_email': user_email,
                    'records_deleted': result.get('total_records_deleted', 0),
                    'verification_hash': result.get('verification_hash')
                }
            )
            
            return result
    
    def perform_sox_compliance_check_with_monitoring(self, tenant_id: int,
                                                   user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Perform SOX compliance check with monitoring
        
        Args:
            tenant_id: Tenant ID
            user_id: User performing the check
            
        Returns:
            SOX compliance check results
        """
        with self.monitor_with_compliance(
            operation_type='sox_compliance_check',
            tenant_id=tenant_id,
            regulation=ComplianceRegulation.SOX,
            data_category=DataCategory.FINANCIAL_DATA,
            affected_records=['sox_compliance'],
            user_id=user_id
        ):
            result = self.compliance_service.implement_sox_compliance_features(tenant_id)
            
            # Trigger alert based on compliance status
            if result['overall_compliant']:
                severity = AlertSeverity.LOW
                title = "SOX Compliance Check Passed"
                description = f"SOX compliance check passed for tenant {tenant_id}"
            else:
                severity = AlertSeverity.HIGH
                title = "SOX Compliance Check Failed"
                description = f"SOX compliance issues detected for tenant {tenant_id}"
            
            self.alerting_service.trigger_alert(
                alert_type=AlertType.COMPLIANCE_VIOLATION,
                severity=severity,
                title=title,
                description=description,
                tenant_id=tenant_id,
                affected_systems=['compliance_service'],
                details=result
            )
            
            return result
    
    def get_comprehensive_security_report(self, tenant_id: Optional[int] = None,
                                        days_back: int = 7) -> Dict[str, Any]:
        """
        Generate a comprehensive security report
        
        Args:
            tenant_id: Optional tenant ID
            days_back: Number of days to include in the report
            
        Returns:
            Comprehensive security report
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)
            
            # Collect data from all services
            dashboard = self.generate_security_dashboard(tenant_id)
            
            # Get detailed compliance reports for each regulation
            compliance_reports = {}
            for regulation in ComplianceRegulation:
                try:
                    report = self.compliance_service.export_compliance_report(
                        tenant_id or 0,  # Use 0 for global if no tenant specified
                        regulation,
                        start_date,
                        end_date
                    )
                    compliance_reports[regulation.value] = report
                except Exception as e:
                    self.logger.warning(f"Could not generate {regulation.value} report: {str(e)}")
            
            # Get monitoring metrics export
            monitoring_metrics = self.monitoring_service.export_metrics(
                format_type='json',
                time_window_hours=days_back * 24
            )
            
            comprehensive_report = {
                'report_metadata': {
                    'generated_at': datetime.utcnow().isoformat(),
                    'tenant_id': tenant_id,
                    'report_period_days': days_back,
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat()
                },
                'executive_summary': {
                    'security_score': dashboard['security_score'],
                    'health_status': dashboard['health_status']['status'],
                    'total_alerts': dashboard['alert_summary']['active_alerts'],
                    'critical_issues': dashboard['alert_summary']['critical_alerts'],
                    'compliance_status': 'compliant' if all(
                        report.get('summary', {}).get('success_rate', 0) > 0.95
                        for report in compliance_reports.values()
                    ) else 'non_compliant'
                },
                'security_dashboard': dashboard,
                'compliance_reports': compliance_reports,
                'monitoring_metrics': json.loads(monitoring_metrics) if isinstance(monitoring_metrics, str) else monitoring_metrics,
                'recommendations': self._generate_security_recommendations(dashboard, compliance_reports)
            }
            
            return comprehensive_report
            
        except Exception as e:
            self.logger.error(f"Error generating comprehensive security report: {str(e)}")
            raise SecurityIntegrationError(f"Failed to generate security report: {str(e)}")
    
    def _generate_security_recommendations(self, dashboard: Dict[str, Any],
                                         compliance_reports: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate security recommendations based on current status"""
        recommendations = []
        
        # Check security score
        security_score = dashboard['security_score']['score']
        if security_score < 75:
            recommendations.append({
                'priority': 'high',
                'category': 'security_score',
                'title': 'Improve Overall Security Score',
                'description': f'Current security score is {security_score}/100. Address critical alerts and failed operations.',
                'actions': [
                    'Resolve active critical and high-severity alerts',
                    'Investigate and fix failed encryption operations',
                    'Review and update security policies'
                ]
            })
        
        # Check active alerts
        critical_alerts = dashboard['alert_summary']['critical_alerts']
        if critical_alerts > 0:
            recommendations.append({
                'priority': 'critical',
                'category': 'alerts',
                'title': 'Address Critical Security Alerts',
                'description': f'{critical_alerts} critical security alerts require immediate attention.',
                'actions': [
                    'Review and resolve all critical alerts',
                    'Investigate root causes',
                    'Implement preventive measures'
                ]
            })
        
        # Check performance
        for op_type, stats in dashboard['performance_stats'].items():
            if stats['error_rate'] > 0.05:
                recommendations.append({
                    'priority': 'medium',
                    'category': 'performance',
                    'title': f'High Error Rate in {op_type}',
                    'description': f'Error rate for {op_type} operations is {stats["error_rate"]:.2%}',
                    'actions': [
                        f'Investigate {op_type} operation failures',
                        'Check system resources and dependencies',
                        'Review error logs for patterns'
                    ]
                })
        
        # Check compliance
        for regulation, report in compliance_reports.items():
            success_rate = report.get('summary', {}).get('success_rate', 1.0)
            if success_rate < 0.95:
                recommendations.append({
                    'priority': 'high',
                    'category': 'compliance',
                    'title': f'{regulation.upper()} Compliance Issues',
                    'description': f'Success rate for {regulation} compliance is {success_rate:.1%}',
                    'actions': [
                        f'Review failed {regulation} compliance operations',
                        'Update compliance procedures',
                        'Provide additional staff training'
                    ]
                })
        
        return recommendations


# Global security integration service instance
security_integration = EncryptionSecurityIntegration()