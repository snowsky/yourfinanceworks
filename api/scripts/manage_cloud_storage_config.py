#!/usr/bin/env python3
"""
Cloud Storage Configuration Management Tool

This tool helps manage cloud storage configuration across different environments.
It can generate, validate, and deploy configuration files for development,
staging, and production environments.

Usage:
    python manage_cloud_storage_config.py [command] [options]

Commands:
    generate    Generate configuration for environment
    validate    Validate existing configuration
    deploy      Deploy configuration to environment
    compare     Compare configurations between environments
    backup      Backup current configuration
    restore     Restore configuration from backup
"""

import sys
import os
import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add the API directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from commercial.cloud_storage.config import (
    CloudStorageConfig, 
    StorageProvider,
    CloudStorageConfigurationManager
)


class ConfigurationManager:
    """Manages cloud storage configuration across environments"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.config_dir = Path("config/environments")
        self.backup_dir = Path("config/backups")
        
        # Ensure directories exist
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def log(self, message: str, level: str = "INFO"):
        """Log message if verbose mode is enabled"""
        if self.verbose or level in ["ERROR", "WARNING"]:
            print(f"[{level}] {message}")
    
    def generate_config(self, environment: str, providers: List[str], interactive: bool = False) -> Dict[str, Any]:
        """Generate configuration for specific environment"""
        self.log(f"Generating configuration for {environment} environment...")
        
        config = {}
        
        # Environment-specific defaults
        if environment == "development":
            config.update(self._get_development_defaults())
        elif environment == "staging":
            config.update(self._get_staging_defaults())
        elif environment == "production":
            config.update(self._get_production_defaults())
        
        # Provider-specific configuration
        for provider in providers:
            if interactive:
                provider_config = self._interactive_provider_config(provider, environment)
            else:
                provider_config = self._default_provider_config(provider, environment)
            
            config.update(provider_config)
        
        # Save configuration
        config_file = self.config_dir / f"{environment}.env"
        self._save_env_config(config, config_file)
        
        self.log(f"Configuration saved to {config_file}")
        return config
    
    def _get_development_defaults(self) -> Dict[str, str]:
        """Get default configuration for development environment"""
        return {
            "CLOUD_STORAGE_ENABLED": "false",
            "CLOUD_STORAGE_PRIMARY_PROVIDER": "local",
            "CLOUD_STORAGE_FALLBACK_ENABLED": "true",
            "STORAGE_OPERATION_LOGGING_ENABLED": "true",
            "STORAGE_PERFORMANCE_MONITORING_ENABLED": "false",
            "STORAGE_COST_OPTIMIZATION_ENABLED": "false",
            "STORAGE_AUDIT_LOGGING_ENABLED": "false",
            "STORAGE_TENANT_ISOLATION_ENABLED": "false",
            "STORAGE_MAX_FILE_SIZE": "10485760",  # 10MB
            "STORAGE_PRESIGNED_URL_EXPIRY": "3600"
        }
    
    def _get_staging_defaults(self) -> Dict[str, str]:
        """Get default configuration for staging environment"""
        return {
            "CLOUD_STORAGE_ENABLED": "true",
            "CLOUD_STORAGE_PRIMARY_PROVIDER": "aws_s3",
            "CLOUD_STORAGE_FALLBACK_ENABLED": "true",
            "STORAGE_OPERATION_LOGGING_ENABLED": "true",
            "STORAGE_PERFORMANCE_MONITORING_ENABLED": "true",
            "STORAGE_COST_OPTIMIZATION_ENABLED": "false",
            "STORAGE_AUDIT_LOGGING_ENABLED": "true",
            "STORAGE_TENANT_ISOLATION_ENABLED": "true",
            "STORAGE_MAX_FILE_SIZE": "52428800",  # 50MB
            "STORAGE_PRESIGNED_URL_EXPIRY": "1800"
        }
    
    def _get_production_defaults(self) -> Dict[str, str]:
        """Get default configuration for production environment"""
        return {
            "CLOUD_STORAGE_ENABLED": "true",
            "CLOUD_STORAGE_PRIMARY_PROVIDER": "aws_s3",
            "CLOUD_STORAGE_FALLBACK_ENABLED": "true",
            "STORAGE_OPERATION_LOGGING_ENABLED": "true",
            "STORAGE_PERFORMANCE_MONITORING_ENABLED": "true",
            "STORAGE_COST_OPTIMIZATION_ENABLED": "true",
            "STORAGE_AUDIT_LOGGING_ENABLED": "true",
            "STORAGE_TENANT_ISOLATION_ENABLED": "true",
            "STORAGE_MAX_FILE_SIZE": "104857600",  # 100MB
            "STORAGE_PRESIGNED_URL_EXPIRY": "900",  # 15 minutes
            "STORAGE_TIER_TRANSITION_DAYS": "30",
            "STORAGE_ARCHIVE_DAYS": "365",
            "STORAGE_COST_ALERT_THRESHOLD": "1000.00",
            "STORAGE_CROSS_REGION_REPLICATION_ENABLED": "true",
            "STORAGE_VERSIONING_ENABLED": "true"
        }
    
    def _default_provider_config(self, provider: str, environment: str) -> Dict[str, str]:
        """Get default provider configuration"""
        config = {}
        
        if provider == "aws_s3":
            config.update({
                "AWS_S3_ENABLED": "true",
                "AWS_S3_BUCKET_NAME": f"myapp-{environment}-attachments",
                "AWS_S3_REGION": "us-east-1",
                "AWS_S3_STORAGE_CLASS": "STANDARD",
                "AWS_S3_SERVER_SIDE_ENCRYPTION": "AES256"
            })
            
            if environment == "production":
                config["AWS_S3_SERVER_SIDE_ENCRYPTION"] = "aws:kms"
        
        elif provider == "azure_blob":
            config.update({
                "AZURE_BLOB_ENABLED": "true",
                "AZURE_STORAGE_ACCOUNT_NAME": f"myapp{environment}storage",
                "AZURE_CONTAINER_NAME": "attachments",
                "AZURE_BLOB_TIER": "Hot",
                "AZURE_BLOB_ENCRYPTION_ENABLED": "true"
            })
        
        elif provider == "gcp_storage":
            config.update({
                "GCP_STORAGE_ENABLED": "true",
                "GCP_PROJECT_ID": f"myapp-{environment}",
                "GCP_BUCKET_NAME": f"myapp-{environment}-attachments",
                "GCP_STORAGE_REGION": "us-central1",
                "GCP_STORAGE_CLASS": "STANDARD"
            })
        
        return config
    
    def _interactive_provider_config(self, provider: str, environment: str) -> Dict[str, str]:
        """Get provider configuration interactively"""
        print(f"\n🔧 Configuring {provider.upper()} for {environment}")
        print("-" * 50)
        
        config = {}
        
        if provider == "aws_s3":
            config["AWS_S3_ENABLED"] = "true"
            config["AWS_S3_BUCKET_NAME"] = input(f"S3 Bucket Name [myapp-{environment}-attachments]: ") or f"myapp-{environment}-attachments"
            config["AWS_S3_REGION"] = input("AWS Region [us-east-1]: ") or "us-east-1"
            
            if input("Use IAM roles for authentication? [y/N]: ").lower() != 'y':
                config["AWS_S3_ACCESS_KEY_ID"] = input("AWS Access Key ID: ")
                config["AWS_S3_SECRET_ACCESS_KEY"] = input("AWS Secret Access Key: ")
            
            storage_class = input("Storage Class [STANDARD]: ") or "STANDARD"
            config["AWS_S3_STORAGE_CLASS"] = storage_class
            
            encryption = input("Server-side encryption [AES256]: ") or "AES256"
            config["AWS_S3_SERVER_SIDE_ENCRYPTION"] = encryption
            
            if encryption == "aws:kms":
                kms_key = input("KMS Key ID (optional): ")
                if kms_key:
                    config["AWS_S3_KMS_KEY_ID"] = kms_key
        
        elif provider == "azure_blob":
            config["AZURE_BLOB_ENABLED"] = "true"
            config["AZURE_STORAGE_ACCOUNT_NAME"] = input(f"Storage Account Name [myapp{environment}storage]: ") or f"myapp{environment}storage"
            config["AZURE_CONTAINER_NAME"] = input("Container Name [attachments]: ") or "attachments"
            
            auth_method = input("Authentication method (1=Account Key, 2=Connection String) [1]: ") or "1"
            if auth_method == "1":
                config["AZURE_STORAGE_ACCOUNT_KEY"] = input("Storage Account Key: ")
            else:
                config["AZURE_STORAGE_CONNECTION_STRING"] = input("Connection String: ")
            
            blob_tier = input("Blob Tier [Hot]: ") or "Hot"
            config["AZURE_BLOB_TIER"] = blob_tier
            
            config["AZURE_BLOB_ENCRYPTION_ENABLED"] = "true"
        
        elif provider == "gcp_storage":
            config["GCP_STORAGE_ENABLED"] = "true"
            config["GCP_PROJECT_ID"] = input(f"GCP Project ID [myapp-{environment}]: ") or f"myapp-{environment}"
            config["GCP_BUCKET_NAME"] = input(f"GCS Bucket Name [myapp-{environment}-attachments]: ") or f"myapp-{environment}-attachments"
            config["GCP_STORAGE_REGION"] = input("GCS Region [us-central1]: ") or "us-central1"
            
            auth_method = input("Authentication method (1=Service Account File, 2=JSON, 3=ADC) [3]: ") or "3"
            if auth_method == "1":
                config["GCP_CREDENTIALS_PATH"] = input("Path to service account key file: ")
            elif auth_method == "2":
                print("Paste service account JSON (press Ctrl+D when done):")
                import sys
                config["GCP_CREDENTIALS_JSON"] = sys.stdin.read()
            
            storage_class = input("Storage Class [STANDARD]: ") or "STANDARD"
            config["GCP_STORAGE_CLASS"] = storage_class
        
        return config
    
    def _save_env_config(self, config: Dict[str, str], file_path: Path):
        """Save configuration to .env file"""
        with open(file_path, 'w') as f:
            f.write(f"# Cloud Storage Configuration for {file_path.stem.upper()}\n")
            f.write(f"# Generated on {datetime.now().isoformat()}\n\n")
            
            # Group related settings
            groups = {
                "General Settings": [
                    "CLOUD_STORAGE_ENABLED",
                    "CLOUD_STORAGE_PRIMARY_PROVIDER",
                    "CLOUD_STORAGE_FALLBACK_ENABLED"
                ],
                "AWS S3 Settings": [
                    "AWS_S3_ENABLED",
                    "AWS_S3_BUCKET_NAME",
                    "AWS_S3_REGION",
                    "AWS_S3_ACCESS_KEY_ID",
                    "AWS_S3_SECRET_ACCESS_KEY",
                    "AWS_S3_STORAGE_CLASS",
                    "AWS_S3_SERVER_SIDE_ENCRYPTION",
                    "AWS_S3_KMS_KEY_ID"
                ],
                "Azure Blob Settings": [
                    "AZURE_BLOB_ENABLED",
                    "AZURE_STORAGE_ACCOUNT_NAME",
                    "AZURE_STORAGE_ACCOUNT_KEY",
                    "AZURE_STORAGE_CONNECTION_STRING",
                    "AZURE_CONTAINER_NAME",
                    "AZURE_BLOB_TIER",
                    "AZURE_BLOB_ENCRYPTION_ENABLED"
                ],
                "GCP Storage Settings": [
                    "GCP_STORAGE_ENABLED",
                    "GCP_PROJECT_ID",
                    "GCP_BUCKET_NAME",
                    "GCP_STORAGE_REGION",
                    "GCP_CREDENTIALS_PATH",
                    "GCP_CREDENTIALS_JSON",
                    "GCP_STORAGE_CLASS"
                ],
                "Storage Settings": [
                    "STORAGE_OPERATION_LOGGING_ENABLED",
                    "STORAGE_PERFORMANCE_MONITORING_ENABLED",
                    "STORAGE_COST_OPTIMIZATION_ENABLED",
                    "STORAGE_AUDIT_LOGGING_ENABLED",
                    "STORAGE_TENANT_ISOLATION_ENABLED",
                    "STORAGE_MAX_FILE_SIZE",
                    "STORAGE_PRESIGNED_URL_EXPIRY",
                    "STORAGE_TIER_TRANSITION_DAYS",
                    "STORAGE_ARCHIVE_DAYS",
                    "STORAGE_COST_ALERT_THRESHOLD",
                    "STORAGE_CROSS_REGION_REPLICATION_ENABLED",
                    "STORAGE_VERSIONING_ENABLED"
                ]
            }
            
            for group_name, keys in groups.items():
                group_config = {k: v for k, v in config.items() if k in keys}
                if group_config:
                    f.write(f"# {group_name}\n")
                    for key, value in group_config.items():
                        f.write(f"{key}={value}\n")
                    f.write("\n")
    
    def validate_config(self, environment: str) -> Dict[str, Any]:
        """Validate configuration for specific environment"""
        self.log(f"Validating configuration for {environment} environment...")
        
        config_file = self.config_dir / f"{environment}.env"
        if not config_file.exists():
            return {
                "valid": False,
                "error": f"Configuration file not found: {config_file}"
            }
        
        # Load environment variables from file
        original_env = dict(os.environ)
        try:
            self._load_env_file(config_file)
            
            # Validate configuration
            config = CloudStorageConfig()
            try:
                config.validate()
                result = {'valid': True, 'errors': [], 'warnings': []}
            except ValueError as e:
                result = {'valid': False, 'errors': [str(e)], 'warnings': []}
            
            return result
        
        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)
    
    def _load_env_file(self, file_path: Path):
        """Load environment variables from .env file"""
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
    
    def deploy_config(self, environment: str, target_file: str = ".env") -> bool:
        """Deploy configuration to target environment"""
        self.log(f"Deploying {environment} configuration to {target_file}...")
        
        config_file = self.config_dir / f"{environment}.env"
        if not config_file.exists():
            self.log(f"Configuration file not found: {config_file}", "ERROR")
            return False
        
        # Backup existing configuration
        target_path = Path(target_file)
        if target_path.exists():
            backup_name = f"{target_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(target_path, backup_name)
            self.log(f"Backed up existing configuration to {backup_name}")
        
        # Deploy new configuration
        shutil.copy2(config_file, target_path)
        self.log(f"Deployed {environment} configuration to {target_file}")
        
        return True
    
    def compare_configs(self, env1: str, env2: str) -> Dict[str, Any]:
        """Compare configurations between two environments"""
        self.log(f"Comparing configurations: {env1} vs {env2}")
        
        config1_file = self.config_dir / f"{env1}.env"
        config2_file = self.config_dir / f"{env2}.env"
        
        if not config1_file.exists():
            return {"error": f"Configuration file not found: {config1_file}"}
        
        if not config2_file.exists():
            return {"error": f"Configuration file not found: {config2_file}"}
        
        config1 = self._parse_env_file(config1_file)
        config2 = self._parse_env_file(config2_file)
        
        # Find differences
        all_keys = set(config1.keys()) | set(config2.keys())
        differences = {}
        
        for key in all_keys:
            val1 = config1.get(key)
            val2 = config2.get(key)
            
            if val1 != val2:
                differences[key] = {
                    env1: val1,
                    env2: val2
                }
        
        return {
            "environment1": env1,
            "environment2": env2,
            "differences": differences,
            "total_differences": len(differences)
        }
    
    def _parse_env_file(self, file_path: Path) -> Dict[str, str]:
        """Parse .env file and return key-value pairs"""
        config = {}
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key] = value
        return config
    
    def backup_config(self, source_file: str = ".env") -> str:
        """Backup current configuration"""
        source_path = Path(source_file)
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_file}")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{source_path.stem}_backup_{timestamp}{source_path.suffix}"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(source_path, backup_path)
        self.log(f"Configuration backed up to {backup_path}")
        
        return str(backup_path)
    
    def restore_config(self, backup_file: str, target_file: str = ".env") -> bool:
        """Restore configuration from backup"""
        backup_path = Path(backup_file)
        if not backup_path.exists():
            self.log(f"Backup file not found: {backup_file}", "ERROR")
            return False
        
        target_path = Path(target_file)
        
        # Backup current file before restore
        if target_path.exists():
            current_backup = self.backup_config(target_file)
            self.log(f"Current configuration backed up to {current_backup}")
        
        # Restore from backup
        shutil.copy2(backup_path, target_path)
        self.log(f"Configuration restored from {backup_file}")
        
        return True
    
    def list_configs(self) -> List[str]:
        """List available configuration files"""
        configs = []
        for file_path in self.config_dir.glob("*.env"):
            configs.append(file_path.stem)
        return sorted(configs)
    
    def list_backups(self) -> List[str]:
        """List available backup files"""
        backups = []
        for file_path in self.backup_dir.glob("*_backup_*"):
            backups.append(str(file_path))
        return sorted(backups, reverse=True)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Cloud storage configuration management tool"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate configuration')
    generate_parser.add_argument('environment', choices=['development', 'staging', 'production'])
    generate_parser.add_argument('--providers', nargs='+', 
                               choices=['aws_s3', 'azure_blob', 'gcp_storage'],
                               default=['aws_s3'], help='Cloud providers to configure')
    generate_parser.add_argument('--interactive', action='store_true', 
                               help='Interactive configuration')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate configuration')
    validate_parser.add_argument('environment', help='Environment to validate')
    
    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy configuration')
    deploy_parser.add_argument('environment', help='Environment to deploy')
    deploy_parser.add_argument('--target', default='.env', help='Target file')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare configurations')
    compare_parser.add_argument('env1', help='First environment')
    compare_parser.add_argument('env2', help='Second environment')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Backup configuration')
    backup_parser.add_argument('--source', default='.env', help='Source file')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore configuration')
    restore_parser.add_argument('backup_file', help='Backup file to restore')
    restore_parser.add_argument('--target', default='.env', help='Target file')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List configurations or backups')
    list_parser.add_argument('type', choices=['configs', 'backups'], help='What to list')
    
    # Global options
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Create configuration manager
    manager = ConfigurationManager(verbose=args.verbose)
    
    try:
        if args.command == 'generate':
            config = manager.generate_config(
                args.environment, 
                args.providers, 
                args.interactive
            )
            print(f"✅ Generated configuration for {args.environment}")
            
        elif args.command == 'validate':
            result = manager.validate_config(args.environment)
            if result.get('valid'):
                print(f"✅ Configuration for {args.environment} is valid")
            else:
                print(f"❌ Configuration for {args.environment} is invalid")
                if result.get('error'):
                    print(f"Error: {result['error']}")
                for error in result.get('errors', []):
                    print(f"  • {error}")
            
        elif args.command == 'deploy':
            success = manager.deploy_config(args.environment, args.target)
            if success:
                print(f"✅ Deployed {args.environment} configuration")
            else:
                print(f"❌ Failed to deploy {args.environment} configuration")
            
        elif args.command == 'compare':
            result = manager.compare_configs(args.env1, args.env2)
            if 'error' in result:
                print(f"❌ {result['error']}")
            else:
                print(f"📊 Comparing {args.env1} vs {args.env2}")
                print(f"Total differences: {result['total_differences']}")
                
                for key, values in result['differences'].items():
                    print(f"\n{key}:")
                    print(f"  {args.env1}: {values[args.env1]}")
                    print(f"  {args.env2}: {values[args.env2]}")
            
        elif args.command == 'backup':
            backup_file = manager.backup_config(args.source)
            print(f"✅ Configuration backed up to {backup_file}")
            
        elif args.command == 'restore':
            success = manager.restore_config(args.backup_file, args.target)
            if success:
                print(f"✅ Configuration restored from {args.backup_file}")
            else:
                print(f"❌ Failed to restore configuration")
            
        elif args.command == 'list':
            if args.type == 'configs':
                configs = manager.list_configs()
                print("📁 Available configurations:")
                for config in configs:
                    print(f"  • {config}")
            else:
                backups = manager.list_backups()
                print("💾 Available backups:")
                for backup in backups:
                    print(f"  • {backup}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()