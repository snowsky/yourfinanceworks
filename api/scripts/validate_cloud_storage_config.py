#!/usr/bin/env python3
"""
Cloud Storage Configuration Validation Script

This script validates cloud storage configuration and tests connectivity
to configured providers. It can be used during deployment to ensure
proper setup before starting the application.

Usage:
    python validate_cloud_storage_config.py [--provider PROVIDER] [--fix-permissions] [--verbose]
"""

import sys
import os
import argparse
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add the API directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commercial.cloud_storage.config import (
    CloudStorageConfig, 
    StorageProvider,
    CloudStorageConfigurationManager
)


class CloudStorageSetupValidator:
    """Validates cloud storage setup and connectivity"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.config = CloudStorageConfig()
        self.config_manager = CloudStorageConfigurationManager()
        self.results: Dict[str, Any] = {}
    
    def log(self, message: str, level: str = "INFO"):
        """Log message if verbose mode is enabled"""
        if self.verbose or level in ["ERROR", "WARNING"]:
            print(f"[{level}] {message}")
    
    async def validate_all(self) -> Dict[str, Any]:
        """Run complete validation suite"""
        self.log("Starting cloud storage configuration validation...")
        
        # Step 1: Validate configuration syntax
        try:
            self.config.validate()
            config_validation = {'valid': True, 'errors': [], 'warnings': []}
        except ValueError as e:
            config_validation = {'valid': False, 'errors': [str(e)], 'warnings': []}
        
        self.results['config_validation'] = config_validation
        
        if not config_validation['valid']:
            self.log("Configuration validation failed:", "ERROR")
            for error in config_validation['errors']:
                self.log(f"  - {error}", "ERROR")
            return self.results
        
        self.log("Configuration validation passed")
        
        # Step 2: Test provider connectivity
        connectivity_results = await self._test_provider_connectivity()
        self.results['connectivity'] = connectivity_results
        
        # Step 3: Validate permissions
        permission_results = await self._validate_permissions()
        self.results['permissions'] = permission_results
        
        # Step 4: Test file operations
        operation_results = await self._test_file_operations()
        self.results['operations'] = operation_results
        
        # Step 5: Generate summary
        self.results['summary'] = self._generate_summary()
        
        return self.results
    
    async def _test_provider_connectivity(self) -> Dict[str, Any]:
        """Test connectivity to all enabled providers"""
        self.log("Testing provider connectivity...")
        results = {}
        
        enabled_providers = self.config.get_enabled_providers()
        provider_configs = {}
        for provider in enabled_providers:
            provider_configs[provider] = self.config.get_provider_config(provider)
        
        for provider, config in provider_configs.items():
            test_result = self.config_manager.test_provider_connection(provider, config)
            results[provider.value] = test_result
        
        return results
    

    
    async def _validate_permissions(self) -> Dict[str, Any]:
        """Validate permissions for all providers"""
        self.log("Validating permissions...")
        
        # This would test actual read/write permissions
        # For now, return a placeholder
        return {
            'tested': False,
            'message': "Permission validation not implemented yet"
        }
    
    async def _test_file_operations(self) -> Dict[str, Any]:
        """Test basic file operations"""
        self.log("Testing file operations...")
        
        # This would test actual file upload/download/delete operations
        # For now, return a placeholder
        return {
            'tested': False,
            'message': "File operation testing not implemented yet"
        }
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate validation summary"""
        config_valid = self.results.get('config_validation', {}).get('valid', False)
        
        connectivity_results = self.results.get('connectivity', {})
        connected_providers = [
            provider for provider, result in connectivity_results.items()
            if result.get('success', False)
        ]
        
        failed_providers = [
            provider for provider, result in connectivity_results.items()
            if not result.get('success', False)
        ]
        
        overall_success = config_valid and len(failed_providers) == 0
        
        return {
            'overall_success': overall_success,
            'config_valid': config_valid,
            'connected_providers': connected_providers,
            'failed_providers': failed_providers,
            'recommendations': self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate setup recommendations"""
        recommendations = []
        
        config_validation = self.results.get('config_validation', {})
        if config_validation.get('errors'):
            recommendations.append("Fix configuration errors before proceeding")
        
        if config_validation.get('warnings'):
            recommendations.append("Review configuration warnings")
        
        connectivity_results = self.results.get('connectivity', {})
        for provider, result in connectivity_results.items():
            if not result.get('success', False):
                recommendations.append(f"Fix {provider} connectivity issues")
        
        if not recommendations:
            recommendations.append("Configuration looks good!")
        
        return recommendations


def print_results(results: Dict[str, Any]):
    """Print validation results in a readable format"""
    print("\n" + "="*60)
    print("CLOUD STORAGE CONFIGURATION VALIDATION RESULTS")
    print("="*60)
    
    # Configuration validation
    config_validation = results.get('config_validation', {})
    print(f"\n📋 Configuration Validation: {'✅ PASSED' if config_validation.get('valid') else '❌ FAILED'}")
    
    if config_validation.get('errors'):
        print("\n❌ Configuration Errors:")
        for error in config_validation['errors']:
            print(f"   • {error}")
    
    if config_validation.get('warnings'):
        print("\n⚠️  Configuration Warnings:")
        for warning in config_validation['warnings']:
            print(f"   • {warning}")
    
    # Connectivity results
    connectivity_results = results.get('connectivity', {})
    if connectivity_results:
        print(f"\n🔗 Provider Connectivity:")
        for provider, result in connectivity_results.items():
            status = "✅ CONNECTED" if result.get('success') else "❌ FAILED"
            print(f"   {provider}: {status}")
            
            if result.get('message'):
                print(f"      {result['message']}")
            if result.get('error'):
                print(f"      Error: {result['error']}")
    
    # Summary
    summary = results.get('summary', {})
    if summary:
        print(f"\n📊 Summary:")
        print(f"   Overall Status: {'✅ SUCCESS' if summary.get('overall_success') else '❌ NEEDS ATTENTION'}")
        
        if summary.get('connected_providers'):
            print(f"   Connected Providers: {', '.join(summary['connected_providers'])}")
        
        if summary.get('failed_providers'):
            print(f"   Failed Providers: {', '.join(summary['failed_providers'])}")
        
        if summary.get('recommendations'):
            print(f"\n💡 Recommendations:")
            for rec in summary['recommendations']:
                print(f"   • {rec}")
    
    print("\n" + "="*60)


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Validate cloud storage configuration and connectivity"
    )
    parser.add_argument(
        '--provider',
        choices=['aws_s3', 'azure_blob', 'gcp_storage', 'local'],
        help="Test specific provider only"
    )
    parser.add_argument(
        '--fix-permissions',
        action='store_true',
        help="Attempt to fix permission issues (not implemented)"
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
    
    # Create validator
    validator = CloudStorageSetupValidator(verbose=args.verbose)
    
    # Run validation
    try:
        results = await validator.validate_all()
        
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print_results(results)
        
        # Exit with appropriate code
        summary = results.get('summary', {})
        exit_code = 0 if summary.get('overall_success') else 1
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\nValidation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Validation failed with error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())