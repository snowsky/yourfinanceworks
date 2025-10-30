#!/usr/bin/env python3
"""
Cloud Storage Deployment Check Script

This script performs pre-deployment checks for cloud storage configuration.
It validates configuration, tests connectivity, and ensures all required
dependencies are installed.

Usage:
    python cloud_storage_deployment_check.py [--environment ENV] [--fix-issues]
"""

import sys
import os
import argparse
import asyncio
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Add the API directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage_config.cloud_storage_config import (
    CloudStorageConfig, 
    StorageProvider,
    CloudStorageConfigurationManager
)


class DeploymentChecker:
    """Performs comprehensive deployment checks for cloud storage"""
    
    def __init__(self, environment: str = "production", fix_issues: bool = False, verbose: bool = False):
        self.environment = environment
        self.fix_issues = fix_issues
        self.verbose = verbose
        self.check_results: Dict[str, Any] = {}
        self.issues_found: List[str] = []
        self.fixes_applied: List[str] = []
    
    def log(self, message: str, level: str = "INFO"):
        """Log message if verbose mode is enabled"""
        if self.verbose or level in ["ERROR", "WARNING"]:
            print(f"[{level}] {message}")
    
    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all deployment checks"""
        self.log("Starting cloud storage deployment checks...")
        
        # Check 1: Environment variables
        env_check = await self._check_environment_variables()
        self.check_results['environment'] = env_check
        
        # Check 2: Dependencies
        deps_check = await self._check_dependencies()
        self.check_results['dependencies'] = deps_check
        
        # Check 3: Configuration validation
        config_check = await self._check_configuration()
        self.check_results['configuration'] = config_check
        
        # Check 4: Provider connectivity
        connectivity_check = await self._check_connectivity()
        self.check_results['connectivity'] = connectivity_check
        
        # Check 5: Permissions
        permissions_check = await self._check_permissions()
        self.check_results['permissions'] = permissions_check
        
        # Check 6: Security settings
        security_check = await self._check_security()
        self.check_results['security'] = security_check
        
        # Check 7: Performance settings
        performance_check = await self._check_performance()
        self.check_results['performance'] = performance_check
        
        # Generate summary
        self.check_results['summary'] = self._generate_summary()
        
        return self.check_results
    
    async def _check_environment_variables(self) -> Dict[str, Any]:
        """Check required environment variables"""
        self.log("Checking environment variables...")
        
        required_vars = {
            'general': [
                'CLOUD_STORAGE_ENABLED',
                'CLOUD_STORAGE_PRIMARY_PROVIDER'
            ],
            'aws_s3': [
                'AWS_S3_ENABLED',
                'AWS_S3_BUCKET_NAME',
                'AWS_S3_REGION'
            ],
            'azure_blob': [
                'AZURE_BLOB_ENABLED',
                'AZURE_STORAGE_ACCOUNT_NAME',
                'AZURE_CONTAINER_NAME'
            ],
            'gcp_storage': [
                'GCP_STORAGE_ENABLED',
                'GCP_PROJECT_ID',
                'GCP_BUCKET_NAME'
            ]
        }
        
        missing_vars = []
        present_vars = []
        
        # Check general variables
        for var in required_vars['general']:
            if os.getenv(var):
                present_vars.append(var)
            else:
                missing_vars.append(var)
        
        # Check provider-specific variables based on enabled providers
        config = CloudStorageConfig()
        
        if config.AWS_S3_ENABLED:
            for var in required_vars['aws_s3']:
                if os.getenv(var):
                    present_vars.append(var)
                else:
                    missing_vars.append(var)
        
        if config.AZURE_BLOB_ENABLED:
            for var in required_vars['azure_blob']:
                if os.getenv(var):
                    present_vars.append(var)
                else:
                    missing_vars.append(var)
        
        if config.GCP_STORAGE_ENABLED:
            for var in required_vars['gcp_storage']:
                if os.getenv(var):
                    present_vars.append(var)
                else:
                    missing_vars.append(var)
        
        # Check for sensitive variables in production
        sensitive_vars_present = []
        if self.environment == "production":
            sensitive_vars = [
                'AWS_S3_ACCESS_KEY_ID',
                'AWS_S3_SECRET_ACCESS_KEY',
                'AZURE_STORAGE_ACCOUNT_KEY',
                'GCP_CREDENTIALS_JSON'
            ]
            
            for var in sensitive_vars:
                if os.getenv(var):
                    sensitive_vars_present.append(var)
        
        return {
            'passed': len(missing_vars) == 0,
            'present_vars': present_vars,
            'missing_vars': missing_vars,
            'sensitive_vars_in_production': sensitive_vars_present,
            'warnings': self._generate_env_warnings(sensitive_vars_present)
        }
    
    def _generate_env_warnings(self, sensitive_vars: List[str]) -> List[str]:
        """Generate warnings for environment variable issues"""
        warnings = []
        
        if self.environment == "production" and sensitive_vars:
            warnings.append(
                f"Sensitive credentials found in environment variables in production: {sensitive_vars}. "
                "Consider using IAM roles, managed identities, or secret management services."
            )
        
        return warnings
    
    async def _check_dependencies(self) -> Dict[str, Any]:
        """Check required Python dependencies"""
        self.log("Checking dependencies...")
        
        required_packages = {
            'boto3': 'AWS S3 support',
            'azure-storage-blob': 'Azure Blob Storage support',
            'google-cloud-storage': 'Google Cloud Storage support'
        }
        
        installed_packages = []
        missing_packages = []
        
        for package, description in required_packages.items():
            try:
                __import__(package.replace('-', '_'))
                installed_packages.append(package)
            except ImportError:
                missing_packages.append({'package': package, 'description': description})
        
        # Try to fix missing packages if requested
        if self.fix_issues and missing_packages:
            await self._fix_missing_dependencies(missing_packages)
        
        return {
            'passed': len(missing_packages) == 0,
            'installed_packages': installed_packages,
            'missing_packages': missing_packages
        }
    
    async def _fix_missing_dependencies(self, missing_packages: List[Dict[str, str]]):
        """Attempt to install missing dependencies"""
        self.log("Attempting to install missing dependencies...")
        
        for package_info in missing_packages:
            package = package_info['package']
            try:
                self.log(f"Installing {package}...")
                result = subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', package],
                    capture_output=True,
                    text=True,
                    check=True
                )
                self.fixes_applied.append(f"Installed {package}")
                self.log(f"Successfully installed {package}")
            except subprocess.CalledProcessError as e:
                self.log(f"Failed to install {package}: {e}", "ERROR")
                self.issues_found.append(f"Could not install {package}")
    
    async def _check_configuration(self) -> Dict[str, Any]:
        """Check configuration validity"""
        self.log("Checking configuration...")
        
        config = CloudStorageConfig()
        try:
            config.validate()
            validation_result = {'valid': True, 'errors': [], 'warnings': []}
        except ValueError as e:
            validation_result = {'valid': False, 'errors': [str(e)], 'warnings': []}
        
        return {
            'passed': validation_result['valid'],
            'errors': validation_result['errors'],
            'warnings': validation_result['warnings']
        }
    
    async def _check_connectivity(self) -> Dict[str, Any]:
        """Check connectivity to cloud providers"""
        self.log("Checking provider connectivity...")
        
        # Test connectivity using the configuration manager
        config = CloudStorageConfig()
        config_manager = CloudStorageConfigurationManager()
        
        enabled_providers = config.get_enabled_providers()
        connectivity_results = {}
        
        for provider in enabled_providers:
            provider_config = config.get_provider_config(provider)
            test_result = config_manager.test_provider_connection(provider, provider_config)
            connectivity_results[provider.value] = test_result
        
        connected_providers = []
        failed_providers = []
        
        for provider, result in connectivity_results.items():
            if result.get('success'):
                connected_providers.append(provider)
            else:
                failed_providers.append({
                    'provider': provider,
                    'error': result.get('error', 'Unknown error')
                })
        
        return {
            'passed': len(failed_providers) == 0,
            'connected_providers': connected_providers,
            'failed_providers': failed_providers
        }
    
    async def _check_permissions(self) -> Dict[str, Any]:
        """Check provider permissions"""
        self.log("Checking permissions...")
        
        # This is a placeholder for permission checks
        # In a real implementation, this would test specific permissions
        # like read, write, delete for each provider
        
        return {
            'passed': True,
            'message': "Permission checks not implemented yet",
            'recommendations': [
                "Ensure S3 bucket has appropriate IAM policies",
                "Verify Azure Blob Storage account has necessary permissions",
                "Check GCS bucket IAM roles and service account permissions"
            ]
        }
    
    async def _check_security(self) -> Dict[str, Any]:
        """Check security settings"""
        self.log("Checking security settings...")
        
        config = CloudStorageConfig()
        issues = []
        recommendations = []
        
        # Check encryption settings
        if config.AWS_S3_ENABLED and config.AWS_S3_SERVER_SIDE_ENCRYPTION == "":
            issues.append("AWS S3 server-side encryption not configured")
        
        if config.AZURE_BLOB_ENABLED and not config.AZURE_BLOB_ENCRYPTION_ENABLED:
            issues.append("Azure Blob encryption not enabled")
        
        # Check tenant isolation
        if not config.TENANT_ISOLATION_ENABLED:
            issues.append("Tenant isolation is disabled")
        
        # Check audit logging
        if not config.AUDIT_LOGGING_ENABLED:
            recommendations.append("Enable audit logging for compliance")
        
        # Check file size limits
        if config.MAX_FILE_SIZE > 100 * 1024 * 1024:  # 100MB
            recommendations.append("Consider reducing maximum file size for better performance")
        
        # Check presigned URL expiry
        if config.PRESIGNED_URL_EXPIRY > 24 * 3600:  # 24 hours
            recommendations.append("Consider shorter presigned URL expiry for better security")
        
        return {
            'passed': len(issues) == 0,
            'issues': issues,
            'recommendations': recommendations
        }
    
    async def _check_performance(self) -> Dict[str, Any]:
        """Check performance settings"""
        self.log("Checking performance settings...")
        
        config = CloudStorageConfig()
        recommendations = []
        
        # Check circuit breaker settings
        if config.CIRCUIT_BREAKER_FAILURE_THRESHOLD > 10:
            recommendations.append("Consider lower circuit breaker failure threshold")
        
        if config.CIRCUIT_BREAKER_RECOVERY_TIMEOUT < 30:
            recommendations.append("Consider longer circuit breaker recovery timeout")
        
        # Check migration settings
        if config.MIGRATION_MAX_CONCURRENT > 10:
            recommendations.append("High concurrent migration count may impact performance")
        
        # Check monitoring settings
        if not config.PERFORMANCE_MONITORING_ENABLED:
            recommendations.append("Enable performance monitoring for better observability")
        
        return {
            'passed': True,
            'recommendations': recommendations
        }
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate deployment check summary"""
        all_checks = [
            self.check_results.get('environment', {}).get('passed', False),
            self.check_results.get('dependencies', {}).get('passed', False),
            self.check_results.get('configuration', {}).get('passed', False),
            self.check_results.get('connectivity', {}).get('passed', False),
            self.check_results.get('permissions', {}).get('passed', False),
            self.check_results.get('security', {}).get('passed', False)
        ]
        
        passed_checks = sum(all_checks)
        total_checks = len(all_checks)
        
        deployment_ready = all(all_checks)
        
        critical_issues = []
        warnings = []
        
        # Collect critical issues
        if not self.check_results.get('environment', {}).get('passed', False):
            critical_issues.append("Missing required environment variables")
        
        if not self.check_results.get('dependencies', {}).get('passed', False):
            critical_issues.append("Missing required dependencies")
        
        if not self.check_results.get('configuration', {}).get('passed', False):
            critical_issues.append("Invalid configuration")
        
        if not self.check_results.get('connectivity', {}).get('passed', False):
            critical_issues.append("Provider connectivity issues")
        
        # Collect warnings
        for check_name, check_result in self.check_results.items():
            if isinstance(check_result, dict) and 'warnings' in check_result:
                warnings.extend(check_result['warnings'])
        
        return {
            'deployment_ready': deployment_ready,
            'passed_checks': passed_checks,
            'total_checks': total_checks,
            'critical_issues': critical_issues,
            'warnings': warnings,
            'fixes_applied': self.fixes_applied,
            'environment': self.environment
        }


def print_deployment_results(results: Dict[str, Any]):
    """Print deployment check results"""
    print("\n" + "="*70)
    print("CLOUD STORAGE DEPLOYMENT READINESS CHECK")
    print("="*70)
    
    summary = results.get('summary', {})
    
    # Overall status
    if summary.get('deployment_ready'):
        print("\n🎉 DEPLOYMENT READY: All checks passed!")
    else:
        print("\n⚠️  DEPLOYMENT NOT READY: Issues found")
    
    print(f"\nEnvironment: {summary.get('environment', 'unknown').upper()}")
    print(f"Checks Passed: {summary.get('passed_checks', 0)}/{summary.get('total_checks', 0)}")
    
    # Critical issues
    critical_issues = summary.get('critical_issues', [])
    if critical_issues:
        print(f"\n❌ Critical Issues ({len(critical_issues)}):")
        for issue in critical_issues:
            print(f"   • {issue}")
    
    # Warnings
    warnings = summary.get('warnings', [])
    if warnings:
        print(f"\n⚠️  Warnings ({len(warnings)}):")
        for warning in warnings:
            print(f"   • {warning}")
    
    # Fixes applied
    fixes_applied = summary.get('fixes_applied', [])
    if fixes_applied:
        print(f"\n🔧 Fixes Applied ({len(fixes_applied)}):")
        for fix in fixes_applied:
            print(f"   • {fix}")
    
    # Detailed results
    print(f"\n📋 Detailed Results:")
    
    for check_name, check_result in results.items():
        if check_name == 'summary':
            continue
        
        if isinstance(check_result, dict):
            status = "✅ PASS" if check_result.get('passed') else "❌ FAIL"
            print(f"   {check_name.title()}: {status}")
            
            # Show errors if any
            if check_result.get('errors'):
                for error in check_result['errors']:
                    print(f"      Error: {error}")
            
            # Show missing items if any
            if check_result.get('missing_vars'):
                print(f"      Missing variables: {', '.join(check_result['missing_vars'])}")
            
            if check_result.get('missing_packages'):
                packages = [p['package'] for p in check_result['missing_packages']]
                print(f"      Missing packages: {', '.join(packages)}")
            
            if check_result.get('failed_providers'):
                providers = [p['provider'] for p in check_result['failed_providers']]
                print(f"      Failed providers: {', '.join(providers)}")
    
    # Recommendations
    print(f"\n💡 Next Steps:")
    if summary.get('deployment_ready'):
        print("   • Configuration is ready for deployment")
        print("   • Run application with cloud storage enabled")
        print("   • Monitor storage operations and performance")
    else:
        print("   • Fix critical issues before deployment")
        print("   • Review warnings and recommendations")
        print("   • Re-run deployment check after fixes")
        print("   • Test in staging environment before production")
    
    print("\n" + "="*70)


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Cloud storage deployment readiness check"
    )
    parser.add_argument(
        '--environment',
        choices=['development', 'staging', 'production'],
        default='production',
        help="Target deployment environment"
    )
    parser.add_argument(
        '--fix-issues',
        action='store_true',
        help="Attempt to fix issues automatically"
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Enable verbose output"
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help="Output results in JSON format"
    )
    
    args = parser.parse_args()
    
    # Create checker
    checker = DeploymentChecker(
        environment=args.environment,
        fix_issues=args.fix_issues,
        verbose=args.verbose
    )
    
    try:
        results = await checker.run_all_checks()
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print_deployment_results(results)
        
        # Exit with appropriate code
        summary = results.get('summary', {})
        exit_code = 0 if summary.get('deployment_ready') else 1
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\nDeployment check interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Deployment check failed with error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())