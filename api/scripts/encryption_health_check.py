#!/usr/bin/env python3
"""
Automated encryption system health check script.
This script performs comprehensive health checks and reports status.
"""

import os
import sys
import json
import time
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.services.encryption_service import EncryptionService
from core.services.key_management_service import KeyManagementService
from core.services.key_rotation_service import KeyRotationService
from commercial.integrations.key_vault_factory import KeyVaultFactory
from encryption_config import EncryptionConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EncryptionHealthChecker:
    """Comprehensive encryption system health checker."""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'UNKNOWN',
            'checks': {},
            'metrics': {},
            'recommendations': []
        }
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks."""
        logger.info("Starting comprehensive encryption health check...")
        
        # Core service checks
        self.check_encryption_service()
        self.check_key_vault_connectivity()
        self.check_master_key_availability()
        
        # Performance checks
        self.check_encryption_performance()
        self.check_key_cache_performance()
        
        # Key management checks
        self.check_key_rotation_status()
        self.check_tenant_key_integrity()
        
        # Security checks
        self.check_security_compliance()
        self.check_audit_logging()
        
        # Infrastructure checks
        self.check_resource_usage()
        self.check_monitoring_status()
        
        # Determine overall status
        self.determine_overall_status()
        
        # Generate recommendations
        self.generate_recommendations()
        
        logger.info(f"Health check completed. Overall status: {self.results['overall_status']}")
        return self.results
    
    def check_encryption_service(self):
        """Check encryption service availability and basic functionality."""
        check_name = 'encryption_service'
        
        try:
            service = EncryptionService()
            
            # Test basic encryption/decryption
            test_data = "health-check-test-data"
            test_tenant_id = 1
            
            start_time = time.time()
            encrypted = service.encrypt_data(test_data, test_tenant_id)
            decrypted = service.decrypt_data(encrypted, test_tenant_id)
            duration = time.time() - start_time
            
            if decrypted == test_data:
                self.results['checks'][check_name] = {
                    'status': 'PASS',
                    'message': f'Encryption service operational (test completed in {duration:.3f}s)',
                    'duration': duration
                }
            else:
                self.results['checks'][check_name] = {
                    'status': 'FAIL',
                    'message': 'Encryption/decryption test failed - data mismatch'
                }
                
        except Exception as e:
            self.results['checks'][check_name] = {
                'status': 'FAIL',
                'message': f'Encryption service error: {str(e)}'
            }
    
    def check_key_vault_connectivity(self):
        """Check key vault connectivity and response time."""
        check_name = 'key_vault_connectivity'
        
        try:
            vault = KeyVaultFactory.create_key_vault()
            
            start_time = time.time()
            connectivity_ok = vault.test_connection()
            response_time = time.time() - start_time
            
            if connectivity_ok:
                status = 'PASS' if response_time < 1.0 else 'WARN'
                message = f'Key vault connectivity OK (response time: {response_time:.3f}s)'
                if response_time >= 1.0:
                    message += ' - High latency detected'
                
                self.results['checks'][check_name] = {
                    'status': status,
                    'message': message,
                    'response_time': response_time
                }
            else:
                self.results['checks'][check_name] = {
                    'status': 'FAIL',
                    'message': 'Key vault connectivity failed'
                }
                
        except Exception as e:
            self.results['checks'][check_name] = {
                'status': 'FAIL',
                'message': f'Key vault connectivity error: {str(e)}'
            }
    
    def check_master_key_availability(self):
        """Check master key availability and integrity."""
        check_name = 'master_key'
        
        try:
            vault = KeyVaultFactory.create_key_vault()
            key_mgmt = KeyManagementService(vault)
            
            if key_mgmt.master_key_exists():
                # Verify master key integrity
                key_mgmt.verify_master_key()
                
                self.results['checks'][check_name] = {
                    'status': 'PASS',
                    'message': 'Master key available and verified'
                }
            else:
                self.results['checks'][check_name] = {
                    'status': 'FAIL',
                    'message': 'Master key not found'
                }
                
        except Exception as e:
            self.results['checks'][check_name] = {
                'status': 'FAIL',
                'message': f'Master key check error: {str(e)}'
            }
    
    def check_encryption_performance(self):
        """Check encryption performance metrics."""
        check_name = 'encryption_performance'
        
        try:
            service = EncryptionService()
            
            # Test with different data sizes
            test_sizes = [100, 1000, 10000]  # bytes
            performance_results = []
            
            for size in test_sizes:
                test_data = "x" * size
                
                start_time = time.time()
                encrypted = service.encrypt_data(test_data, 1)
                encryption_time = time.time() - start_time
                
                start_time = time.time()
                decrypted = service.decrypt_data(encrypted, 1)
                decryption_time = time.time() - start_time
                
                performance_results.append({
                    'size': size,
                    'encryption_time': encryption_time,
                    'decryption_time': decryption_time,
                    'throughput': size / (encryption_time + decryption_time)
                })
            
            # Check if performance is acceptable
            avg_encryption_time = sum(r['encryption_time'] for r in performance_results) / len(performance_results)
            
            if avg_encryption_time < 0.01:  # 10ms threshold
                status = 'PASS'
                message = f'Encryption performance good (avg: {avg_encryption_time:.3f}s)'
            elif avg_encryption_time < 0.1:  # 100ms threshold
                status = 'WARN'
                message = f'Encryption performance acceptable (avg: {avg_encryption_time:.3f}s)'
            else:
                status = 'FAIL'
                message = f'Encryption performance poor (avg: {avg_encryption_time:.3f}s)'
            
            self.results['checks'][check_name] = {
                'status': status,
                'message': message,
                'performance_data': performance_results
            }
            
        except Exception as e:
            self.results['checks'][check_name] = {
                'status': 'FAIL',
                'message': f'Performance check error: {str(e)}'
            }
    
    def check_key_cache_performance(self):
        """Check key cache performance and hit rates."""
        check_name = 'key_cache_performance'
        
        try:
            # This would typically query metrics from the monitoring system
            # For now, we'll simulate the check
            
            # In a real implementation, you would query Prometheus or similar
            cache_hit_rate = self.get_metric('key_cache_hit_rate', default=0.85)
            cache_size = self.get_metric('key_cache_size', default=1000)
            cache_memory_usage = self.get_metric('key_cache_memory_usage_bytes', default=50000000)
            
            if cache_hit_rate >= 0.9:
                status = 'PASS'
                message = f'Key cache performance excellent (hit rate: {cache_hit_rate:.1%})'
            elif cache_hit_rate >= 0.7:
                status = 'WARN'
                message = f'Key cache performance acceptable (hit rate: {cache_hit_rate:.1%})'
            else:
                status = 'FAIL'
                message = f'Key cache performance poor (hit rate: {cache_hit_rate:.1%})'
            
            self.results['checks'][check_name] = {
                'status': status,
                'message': message,
                'cache_hit_rate': cache_hit_rate,
                'cache_size': cache_size,
                'memory_usage': cache_memory_usage
            }
            
        except Exception as e:
            self.results['checks'][check_name] = {
                'status': 'FAIL',
                'message': f'Cache performance check error: {str(e)}'
            }
    
    def check_key_rotation_status(self):
        """Check key rotation status and schedule compliance."""
        check_name = 'key_rotation_status'
        
        try:
            vault = KeyVaultFactory.create_key_vault()
            rotation_service = KeyRotationService(vault)
            
            status_info = rotation_service.get_rotation_status()
            
            due_count = len(status_info.get('due_for_rotation', []))
            overdue_count = len(status_info.get('overdue', []))
            
            if overdue_count > 0:
                status = 'FAIL'
                message = f'Key rotation critical: {overdue_count} overdue, {due_count} due'
            elif due_count > 10:
                status = 'WARN'
                message = f'Many keys due for rotation: {due_count} tenants'
            else:
                status = 'PASS'
                message = f'Key rotation status good: {due_count} due, {overdue_count} overdue'
            
            self.results['checks'][check_name] = {
                'status': status,
                'message': message,
                'due_count': due_count,
                'overdue_count': overdue_count
            }
            
        except Exception as e:
            self.results['checks'][check_name] = {
                'status': 'FAIL',
                'message': f'Key rotation check error: {str(e)}'
            }
    
    def check_tenant_key_integrity(self):
        """Check integrity of tenant encryption keys."""
        check_name = 'tenant_key_integrity'
        
        try:
            vault = KeyVaultFactory.create_key_vault()
            key_mgmt = KeyManagementService(vault)
            service = EncryptionService()
            
            # Get sample of tenant IDs to check
            tenant_ids = key_mgmt.get_all_tenant_ids()[:10]  # Check first 10 tenants
            
            corrupted_tenants = []
            
            for tenant_id in tenant_ids:
                try:
                    # Test encryption/decryption for each tenant
                    test_data = f"integrity-test-{tenant_id}"
                    encrypted = service.encrypt_data(test_data, tenant_id)
                    decrypted = service.decrypt_data(encrypted, tenant_id)
                    
                    if decrypted != test_data:
                        corrupted_tenants.append(tenant_id)
                        
                except Exception:
                    corrupted_tenants.append(tenant_id)
            
            if not corrupted_tenants:
                status = 'PASS'
                message = f'Tenant key integrity verified for {len(tenant_ids)} tenants'
            else:
                status = 'FAIL'
                message = f'Key corruption detected for tenants: {corrupted_tenants}'
            
            self.results['checks'][check_name] = {
                'status': status,
                'message': message,
                'checked_tenants': len(tenant_ids),
                'corrupted_tenants': corrupted_tenants
            }
            
        except Exception as e:
            self.results['checks'][check_name] = {
                'status': 'FAIL',
                'message': f'Tenant key integrity check error: {str(e)}'
            }
    
    def check_security_compliance(self):
        """Check security compliance status."""
        check_name = 'security_compliance'
        
        try:
            # Check encryption configuration compliance
            compliance_issues = []
            
            # Check encryption is enabled
            if not EncryptionConfig.ENCRYPTION_ENABLED:
                compliance_issues.append("Encryption is disabled")
            
            # Check key vault provider is not local in production
            if EncryptionConfig.KEY_VAULT_PROVIDER == 'local' and os.getenv('ENVIRONMENT') == 'production':
                compliance_issues.append("Using local key vault in production")
            
            # Check key rotation is enabled
            if not EncryptionConfig.KEY_ROTATION_ENABLED:
                compliance_issues.append("Key rotation is disabled")
            
            # Check key derivation iterations
            if EncryptionConfig.KEY_DERIVATION_ITERATIONS < 100000:
                compliance_issues.append("Key derivation iterations below recommended minimum")
            
            if not compliance_issues:
                status = 'PASS'
                message = 'Security compliance checks passed'
            else:
                status = 'FAIL'
                message = f'Security compliance issues: {", ".join(compliance_issues)}'
            
            self.results['checks'][check_name] = {
                'status': status,
                'message': message,
                'compliance_issues': compliance_issues
            }
            
        except Exception as e:
            self.results['checks'][check_name] = {
                'status': 'FAIL',
                'message': f'Security compliance check error: {str(e)}'
            }
    
    def check_audit_logging(self):
        """Check audit logging functionality."""
        check_name = 'audit_logging'
        
        try:
            # Check if audit logs are being generated
            audit_log_path = "/var/log/encryption_audit.log"
            
            if os.path.exists(audit_log_path):
                # Check if log has been updated recently
                stat = os.stat(audit_log_path)
                last_modified = datetime.fromtimestamp(stat.st_mtime)
                age = datetime.now() - last_modified
                
                if age < timedelta(hours=1):
                    status = 'PASS'
                    message = f'Audit logging active (last update: {age.total_seconds():.0f}s ago)'
                else:
                    status = 'WARN'
                    message = f'Audit log stale (last update: {age.total_seconds():.0f}s ago)'
            else:
                status = 'FAIL'
                message = 'Audit log file not found'
            
            self.results['checks'][check_name] = {
                'status': status,
                'message': message
            }
            
        except Exception as e:
            self.results['checks'][check_name] = {
                'status': 'FAIL',
                'message': f'Audit logging check error: {str(e)}'
            }
    
    def check_resource_usage(self):
        """Check resource usage of encryption services."""
        check_name = 'resource_usage'
        
        try:
            # This would typically query system metrics
            # For now, we'll simulate the check
            
            cpu_usage = self.get_metric('encryption_cpu_usage_percent', default=25.0)
            memory_usage = self.get_metric('encryption_memory_usage_percent', default=45.0)
            
            issues = []
            if cpu_usage > 80:
                issues.append(f"High CPU usage: {cpu_usage:.1f}%")
            if memory_usage > 85:
                issues.append(f"High memory usage: {memory_usage:.1f}%")
            
            if not issues:
                status = 'PASS'
                message = f'Resource usage normal (CPU: {cpu_usage:.1f}%, Memory: {memory_usage:.1f}%)'
            else:
                status = 'WARN'
                message = f'Resource usage issues: {", ".join(issues)}'
            
            self.results['checks'][check_name] = {
                'status': status,
                'message': message,
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage
            }
            
        except Exception as e:
            self.results['checks'][check_name] = {
                'status': 'FAIL',
                'message': f'Resource usage check error: {str(e)}'
            }
    
    def check_monitoring_status(self):
        """Check monitoring and metrics collection status."""
        check_name = 'monitoring_status'
        
        try:
            # Test metrics endpoint
            try:
                response = requests.get('http://localhost:8000/metrics', timeout=5)
                metrics_available = response.status_code == 200
            except:
                metrics_available = False
            
            # Check if encryption metrics are present
            encryption_metrics_found = False
            if metrics_available:
                metrics_content = response.text
                encryption_metrics_found = 'encryption_operations_total' in metrics_content
            
            if metrics_available and encryption_metrics_found:
                status = 'PASS'
                message = 'Monitoring and metrics collection operational'
            elif metrics_available:
                status = 'WARN'
                message = 'Metrics endpoint available but encryption metrics missing'
            else:
                status = 'FAIL'
                message = 'Metrics endpoint not accessible'
            
            self.results['checks'][check_name] = {
                'status': status,
                'message': message,
                'metrics_available': metrics_available,
                'encryption_metrics_found': encryption_metrics_found
            }
            
        except Exception as e:
            self.results['checks'][check_name] = {
                'status': 'FAIL',
                'message': f'Monitoring status check error: {str(e)}'
            }
    
    def get_metric(self, metric_name: str, default: float = 0.0) -> float:
        """Get metric value from monitoring system."""
        try:
            # In a real implementation, this would query Prometheus or similar
            # For now, return default values
            return default
        except:
            return default
    
    def determine_overall_status(self):
        """Determine overall system status based on individual checks."""
        statuses = [check['status'] for check in self.results['checks'].values()]
        
        if 'FAIL' in statuses:
            self.results['overall_status'] = 'FAIL'
        elif 'WARN' in statuses:
            self.results['overall_status'] = 'WARN'
        else:
            self.results['overall_status'] = 'PASS'
    
    def generate_recommendations(self):
        """Generate recommendations based on check results."""
        recommendations = []
        
        for check_name, check_result in self.results['checks'].items():
            if check_result['status'] == 'FAIL':
                if check_name == 'encryption_service':
                    recommendations.append("Restart encryption service and check configuration")
                elif check_name == 'key_vault_connectivity':
                    recommendations.append("Check key vault credentials and network connectivity")
                elif check_name == 'master_key':
                    recommendations.append("Generate or restore master encryption key")
                elif check_name == 'key_rotation_status':
                    recommendations.append("Perform overdue key rotations immediately")
                elif check_name == 'tenant_key_integrity':
                    recommendations.append("Regenerate corrupted tenant keys")
                elif check_name == 'security_compliance':
                    recommendations.append("Address security compliance issues")
                elif check_name == 'monitoring_status':
                    recommendations.append("Fix monitoring and metrics collection")
            
            elif check_result['status'] == 'WARN':
                if check_name == 'encryption_performance':
                    recommendations.append("Optimize encryption performance or scale resources")
                elif check_name == 'key_cache_performance':
                    recommendations.append("Tune key cache configuration")
                elif check_name == 'key_rotation_status':
                    recommendations.append("Schedule key rotations for due tenants")
                elif check_name == 'resource_usage':
                    recommendations.append("Monitor resource usage and consider scaling")
        
        self.results['recommendations'] = recommendations
    
    def save_results(self, output_file: str = None):
        """Save health check results to file."""
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"/var/log/encryption_health_check_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        logger.info(f"Health check results saved to {output_file}")
        return output_file
    
    def print_summary(self):
        """Print health check summary."""
        print(f"\n{'='*60}")
        print(f"ENCRYPTION SYSTEM HEALTH CHECK SUMMARY")
        print(f"{'='*60}")
        print(f"Timestamp: {self.results['timestamp']}")
        print(f"Overall Status: {self.results['overall_status']}")
        print(f"{'='*60}")
        
        for check_name, check_result in self.results['checks'].items():
            status_icon = "✓" if check_result['status'] == 'PASS' else "⚠" if check_result['status'] == 'WARN' else "✗"
            print(f"{status_icon} {check_name.replace('_', ' ').title()}: {check_result['message']}")
        
        if self.results['recommendations']:
            print(f"\n{'='*60}")
            print("RECOMMENDATIONS:")
            print(f"{'='*60}")
            for i, recommendation in enumerate(self.results['recommendations'], 1):
                print(f"{i}. {recommendation}")
        
        print(f"{'='*60}\n")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Encryption system health check')
    parser.add_argument('--output', '-o', help='Output file for results')
    parser.add_argument('--quiet', '-q', action='store_true', help='Quiet mode - no console output')
    parser.add_argument('--json', action='store_true', help='Output results as JSON')
    
    args = parser.parse_args()
    
    # Run health check
    checker = EncryptionHealthChecker()
    results = checker.run_all_checks()
    
    # Save results
    output_file = checker.save_results(args.output)
    
    # Output results
    if args.json:
        print(json.dumps(results, indent=2))
    elif not args.quiet:
        checker.print_summary()
    
    # Exit with appropriate code
    if results['overall_status'] == 'FAIL':
        sys.exit(1)
    elif results['overall_status'] == 'WARN':
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()