#!/usr/bin/env python3
"""
Cloud Storage Setup Script

This script helps set up cloud storage providers by creating necessary
resources and configuring permissions. It provides interactive setup
for AWS S3, Azure Blob Storage, and Google Cloud Storage.

Usage:
    python setup_cloud_storage.py [--provider PROVIDER] [--interactive] [--dry-run]
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


class CloudStorageSetup:
    """Interactive cloud storage setup"""
    
    def __init__(self, dry_run: bool = False, verbose: bool = False):
        self.dry_run = dry_run
        self.verbose = verbose
        self.setup_results: Dict[str, Any] = {}
    
    def log(self, message: str, level: str = "INFO"):
        """Log message if verbose mode is enabled"""
        if self.verbose or level in ["ERROR", "WARNING"]:
            prefix = "[DRY RUN] " if self.dry_run else ""
            print(f"{prefix}[{level}] {message}")
    
    def prompt(self, message: str, default: str = "") -> str:
        """Prompt user for input"""
        if default:
            response = input(f"{message} [{default}]: ").strip()
            return response if response else default
        else:
            return input(f"{message}: ").strip()
    
    def confirm(self, message: str) -> bool:
        """Ask for yes/no confirmation"""
        while True:
            response = input(f"{message} (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False
            else:
                print("Please enter 'y' or 'n'")
    
    async def setup_interactive(self) -> Dict[str, Any]:
        """Run interactive setup"""
        print("🚀 Cloud Storage Interactive Setup")
        print("=" * 50)
        
        # Ask which providers to set up
        providers_to_setup = self._select_providers()
        
        for provider in providers_to_setup:
            print(f"\n📦 Setting up {provider.upper()}...")
            
            if provider == "aws_s3":
                await self._setup_aws_s3()
            elif provider == "azure_blob":
                await self._setup_azure_blob()
            elif provider == "gcp_storage":
                await self._setup_gcp_storage()
        
        # Generate environment file
        if self.confirm("\nGenerate .env file with configuration?"):
            self._generate_env_file()
        
        return self.setup_results
    
    def _select_providers(self) -> List[str]:
        """Let user select which providers to set up"""
        print("\nWhich cloud storage providers would you like to set up?")
        print("1. AWS S3")
        print("2. Azure Blob Storage")
        print("3. Google Cloud Storage")
        print("4. All providers")
        
        while True:
            choice = input("\nEnter your choice (1-4): ").strip()
            
            if choice == "1":
                return ["aws_s3"]
            elif choice == "2":
                return ["azure_blob"]
            elif choice == "3":
                return ["gcp_storage"]
            elif choice == "4":
                return ["aws_s3", "azure_blob", "gcp_storage"]
            else:
                print("Invalid choice. Please enter 1-4.")
    
    async def _setup_aws_s3(self):
        """Set up AWS S3 storage"""
        print("\n🔧 AWS S3 Setup")
        print("-" * 20)
        
        config = {}
        
        # Basic configuration
        config['bucket_name'] = self.prompt("S3 Bucket Name")
        config['region'] = self.prompt("AWS Region", "us-east-1")
        
        # Authentication
        print("\nAuthentication options:")
        print("1. Access Key/Secret Key")
        print("2. IAM Role (recommended for production)")
        
        auth_choice = self.prompt("Choose authentication method (1-2)", "2")
        
        if auth_choice == "1":
            config['access_key_id'] = self.prompt("AWS Access Key ID")
            config['secret_access_key'] = self.prompt("AWS Secret Access Key")
        else:
            print("Using IAM role authentication (no keys needed)")
            config['use_iam_role'] = True
        
        # Advanced options
        if self.confirm("Configure advanced options?"):
            config['storage_class'] = self.prompt("Storage Class", "STANDARD")
            config['encryption'] = self.prompt("Server-side encryption", "AES256")
            
            if config['encryption'] == "aws:kms":
                config['kms_key_id'] = self.prompt("KMS Key ID (optional)")
        
        # Test configuration
        if self.confirm("Test S3 configuration?"):
            await self._test_aws_s3_config(config)
        
        self.setup_results['aws_s3'] = config
    
    async def _setup_azure_blob(self):
        """Set up Azure Blob Storage"""
        print("\n🔧 Azure Blob Storage Setup")
        print("-" * 30)
        
        config = {}
        
        # Basic configuration
        config['account_name'] = self.prompt("Storage Account Name")
        config['container_name'] = self.prompt("Container Name", "attachments")
        
        # Authentication
        print("\nAuthentication options:")
        print("1. Account Key")
        print("2. Connection String")
        
        auth_choice = self.prompt("Choose authentication method (1-2)", "1")
        
        if auth_choice == "1":
            config['account_key'] = self.prompt("Storage Account Key")
        else:
            config['connection_string'] = self.prompt("Connection String")
        
        # Advanced options
        if self.confirm("Configure advanced options?"):
            config['blob_tier'] = self.prompt("Blob Tier", "Hot")
            config['encryption_enabled'] = self.confirm("Enable encryption?")
        
        # Test configuration
        if self.confirm("Test Azure Blob configuration?"):
            await self._test_azure_blob_config(config)
        
        self.setup_results['azure_blob'] = config
    
    async def _setup_gcp_storage(self):
        """Set up Google Cloud Storage"""
        print("\n🔧 Google Cloud Storage Setup")
        print("-" * 30)
        
        config = {}
        
        # Basic configuration
        config['project_id'] = self.prompt("GCP Project ID")
        config['bucket_name'] = self.prompt("GCS Bucket Name")
        config['region'] = self.prompt("GCS Region", "us-central1")
        
        # Authentication
        print("\nAuthentication options:")
        print("1. Service Account Key File")
        print("2. Service Account Key JSON")
        print("3. Application Default Credentials")
        
        auth_choice = self.prompt("Choose authentication method (1-3)", "3")
        
        if auth_choice == "1":
            config['credentials_path'] = self.prompt("Path to service account key file")
        elif auth_choice == "2":
            print("Paste the service account key JSON (press Enter twice when done):")
            json_lines = []
            while True:
                line = input()
                if line == "" and json_lines:
                    break
                json_lines.append(line)
            config['credentials_json'] = "\n".join(json_lines)
        else:
            print("Using Application Default Credentials")
            config['use_adc'] = True
        
        # Advanced options
        if self.confirm("Configure advanced options?"):
            config['storage_class'] = self.prompt("Storage Class", "STANDARD")
        
        # Test configuration
        if self.confirm("Test GCS configuration?"):
            await self._test_gcp_storage_config(config)
        
        self.setup_results['gcp_storage'] = config
    
    async def _test_aws_s3_config(self, config: Dict[str, Any]):
        """Test AWS S3 configuration"""
        self.log("Testing AWS S3 configuration...")
        
        if self.dry_run:
            self.log("Skipping S3 test in dry-run mode")
            return
        
        try:
            import boto3
            from botocore.exceptions import ClientError
            
            # Create S3 client
            if config.get('use_iam_role'):
                s3_client = boto3.client('s3', region_name=config['region'])
            else:
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=config['access_key_id'],
                    aws_secret_access_key=config['secret_access_key'],
                    region_name=config['region']
                )
            
            # Test bucket access
            bucket_name = config['bucket_name']
            
            try:
                s3_client.head_bucket(Bucket=bucket_name)
                self.log(f"✅ Successfully connected to S3 bucket: {bucket_name}")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    if self.confirm(f"Bucket {bucket_name} not found. Create it?"):
                        await self._create_s3_bucket(s3_client, config)
                else:
                    self.log(f"❌ S3 test failed: {e}", "ERROR")
            
        except ImportError:
            self.log("❌ boto3 not installed. Run: pip install boto3", "ERROR")
        except Exception as e:
            self.log(f"❌ S3 test failed: {e}", "ERROR")
    
    async def _create_s3_bucket(self, s3_client, config: Dict[str, Any]):
        """Create S3 bucket"""
        bucket_name = config['bucket_name']
        region = config['region']
        
        try:
            if region == 'us-east-1':
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': region}
                )
            
            self.log(f"✅ Created S3 bucket: {bucket_name}")
            
            # Enable versioning if requested
            if self.confirm("Enable versioning on the bucket?"):
                s3_client.put_bucket_versioning(
                    Bucket=bucket_name,
                    VersioningConfiguration={'Status': 'Enabled'}
                )
                self.log("✅ Enabled versioning")
            
            # Set up lifecycle policy if requested
            if self.confirm("Set up lifecycle policy for cost optimization?"):
                await self._setup_s3_lifecycle_policy(s3_client, bucket_name)
            
        except Exception as e:
            self.log(f"❌ Failed to create S3 bucket: {e}", "ERROR")
    
    async def _setup_s3_lifecycle_policy(self, s3_client, bucket_name: str):
        """Set up S3 lifecycle policy"""
        lifecycle_policy = {
            'Rules': [
                {
                    'ID': 'AttachmentLifecycle',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': 'tenant_'},
                    'Transitions': [
                        {
                            'Days': 30,
                            'StorageClass': 'STANDARD_IA'
                        },
                        {
                            'Days': 90,
                            'StorageClass': 'GLACIER'
                        }
                    ]
                }
            ]
        }
        
        try:
            s3_client.put_bucket_lifecycle_configuration(
                Bucket=bucket_name,
                LifecycleConfiguration=lifecycle_policy
            )
            self.log("✅ Set up lifecycle policy")
        except Exception as e:
            self.log(f"❌ Failed to set up lifecycle policy: {e}", "ERROR")
    
    async def _test_azure_blob_config(self, config: Dict[str, Any]):
        """Test Azure Blob Storage configuration"""
        self.log("Testing Azure Blob Storage configuration...")
        
        if self.dry_run:
            self.log("Skipping Azure Blob test in dry-run mode")
            return
        
        try:
            from azure.storage.blob import BlobServiceClient
            from azure.core.exceptions import ResourceNotFoundError
            
            # Create blob service client
            if 'connection_string' in config:
                blob_service_client = BlobServiceClient.from_connection_string(
                    config['connection_string']
                )
            else:
                account_url = f"https://{config['account_name']}.blob.core.windows.net"
                blob_service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=config['account_key']
                )
            
            # Test container access
            container_name = config['container_name']
            
            try:
                container_client = blob_service_client.get_container_client(container_name)
                container_client.get_container_properties()
                self.log(f"✅ Successfully connected to Azure Blob container: {container_name}")
            except ResourceNotFoundError:
                if self.confirm(f"Container {container_name} not found. Create it?"):
                    await self._create_azure_container(blob_service_client, config)
            
        except ImportError:
            self.log("❌ azure-storage-blob not installed. Run: pip install azure-storage-blob", "ERROR")
        except Exception as e:
            self.log(f"❌ Azure Blob test failed: {e}", "ERROR")
    
    async def _create_azure_container(self, blob_service_client, config: Dict[str, Any]):
        """Create Azure Blob container"""
        container_name = config['container_name']
        
        try:
            container_client = blob_service_client.create_container(container_name)
            self.log(f"✅ Created Azure Blob container: {container_name}")
        except Exception as e:
            self.log(f"❌ Failed to create Azure Blob container: {e}", "ERROR")
    
    async def _test_gcp_storage_config(self, config: Dict[str, Any]):
        """Test Google Cloud Storage configuration"""
        self.log("Testing Google Cloud Storage configuration...")
        
        if self.dry_run:
            self.log("Skipping GCS test in dry-run mode")
            return
        
        try:
            from google.cloud import storage
            from google.api_core.exceptions import NotFound
            
            # Create storage client
            if 'credentials_json' in config:
                import json
                from google.oauth2 import service_account
                
                credentials_info = json.loads(config['credentials_json'])
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_info
                )
                client = storage.Client(
                    project=config['project_id'],
                    credentials=credentials
                )
            elif 'credentials_path' in config:
                client = storage.Client.from_service_account_json(
                    config['credentials_path'],
                    project=config['project_id']
                )
            else:
                client = storage.Client(project=config['project_id'])
            
            # Test bucket access
            bucket_name = config['bucket_name']
            
            try:
                bucket = client.bucket(bucket_name)
                bucket.reload()
                self.log(f"✅ Successfully connected to GCS bucket: {bucket_name}")
            except NotFound:
                if self.confirm(f"Bucket {bucket_name} not found. Create it?"):
                    await self._create_gcs_bucket(client, config)
            
        except ImportError:
            self.log("❌ google-cloud-storage not installed. Run: pip install google-cloud-storage", "ERROR")
        except Exception as e:
            self.log(f"❌ GCS test failed: {e}", "ERROR")
    
    async def _create_gcs_bucket(self, client, config: Dict[str, Any]):
        """Create GCS bucket"""
        bucket_name = config['bucket_name']
        region = config['region']
        
        try:
            bucket = client.bucket(bucket_name)
            bucket.storage_class = config.get('storage_class', 'STANDARD')
            bucket = client.create_bucket(bucket, location=region)
            
            self.log(f"✅ Created GCS bucket: {bucket_name}")
            
            # Enable versioning if requested
            if self.confirm("Enable versioning on the bucket?"):
                bucket.versioning_enabled = True
                bucket.patch()
                self.log("✅ Enabled versioning")
            
        except Exception as e:
            self.log(f"❌ Failed to create GCS bucket: {e}", "ERROR")
    
    def _generate_env_file(self):
        """Generate .env file with configuration"""
        env_content = []
        
        env_content.append("# Cloud Storage Configuration")
        env_content.append("# Generated by setup_cloud_storage.py")
        env_content.append("")
        
        # General settings
        env_content.append("# General Settings")
        env_content.append("CLOUD_STORAGE_ENABLED=true")
        
        # Determine primary provider
        if len(self.setup_results) == 1:
            primary_provider = list(self.setup_results.keys())[0]
        else:
            print("\nWhich provider should be primary?")
            for i, provider in enumerate(self.setup_results.keys(), 1):
                print(f"{i}. {provider}")
            
            while True:
                try:
                    choice = int(input("Enter choice: ")) - 1
                    primary_provider = list(self.setup_results.keys())[choice]
                    break
                except (ValueError, IndexError):
                    print("Invalid choice")
        
        env_content.append(f"CLOUD_STORAGE_PRIMARY_PROVIDER={primary_provider}")
        env_content.append("CLOUD_STORAGE_FALLBACK_ENABLED=true")
        env_content.append("")
        
        # AWS S3 configuration
        if 'aws_s3' in self.setup_results:
            config = self.setup_results['aws_s3']
            env_content.append("# AWS S3 Configuration")
            env_content.append("AWS_S3_ENABLED=true")
            env_content.append(f"AWS_S3_BUCKET_NAME={config['bucket_name']}")
            env_content.append(f"AWS_S3_REGION={config['region']}")
            
            if not config.get('use_iam_role'):
                env_content.append(f"AWS_S3_ACCESS_KEY_ID={config.get('access_key_id', '')}")
                env_content.append(f"AWS_S3_SECRET_ACCESS_KEY={config.get('secret_access_key', '')}")
            
            if 'storage_class' in config:
                env_content.append(f"AWS_S3_STORAGE_CLASS={config['storage_class']}")
            
            if 'encryption' in config:
                env_content.append(f"AWS_S3_SERVER_SIDE_ENCRYPTION={config['encryption']}")
            
            if 'kms_key_id' in config:
                env_content.append(f"AWS_S3_KMS_KEY_ID={config['kms_key_id']}")
            
            env_content.append("")
        
        # Azure Blob configuration
        if 'azure_blob' in self.setup_results:
            config = self.setup_results['azure_blob']
            env_content.append("# Azure Blob Storage Configuration")
            env_content.append("AZURE_BLOB_ENABLED=true")
            env_content.append(f"AZURE_CONTAINER_NAME={config['container_name']}")
            
            if 'connection_string' in config:
                env_content.append(f"AZURE_STORAGE_CONNECTION_STRING={config['connection_string']}")
            else:
                env_content.append(f"AZURE_STORAGE_ACCOUNT_NAME={config['account_name']}")
                env_content.append(f"AZURE_STORAGE_ACCOUNT_KEY={config['account_key']}")
            
            if 'blob_tier' in config:
                env_content.append(f"AZURE_BLOB_TIER={config['blob_tier']}")
            
            if 'encryption_enabled' in config:
                env_content.append(f"AZURE_BLOB_ENCRYPTION_ENABLED={str(config['encryption_enabled']).lower()}")
            
            env_content.append("")
        
        # GCP Storage configuration
        if 'gcp_storage' in self.setup_results:
            config = self.setup_results['gcp_storage']
            env_content.append("# Google Cloud Storage Configuration")
            env_content.append("GCP_STORAGE_ENABLED=true")
            env_content.append(f"GCP_PROJECT_ID={config['project_id']}")
            env_content.append(f"GCP_BUCKET_NAME={config['bucket_name']}")
            env_content.append(f"GCP_STORAGE_REGION={config['region']}")
            
            if 'credentials_path' in config:
                env_content.append(f"GCP_CREDENTIALS_PATH={config['credentials_path']}")
            elif 'credentials_json' in config:
                # For JSON credentials, recommend using a file
                env_content.append("# GCP_CREDENTIALS_JSON=<paste_service_account_json_here>")
                env_content.append("# Or use: GCP_CREDENTIALS_PATH=/path/to/service-account-key.json")
            
            if 'storage_class' in config:
                env_content.append(f"GCP_STORAGE_CLASS={config['storage_class']}")
            
            env_content.append("")
        
        # Write to file
        env_file_path = Path(".env.cloud-storage")
        with open(env_file_path, 'w') as f:
            f.write('\n'.join(env_content))
        
        print(f"\n✅ Generated configuration file: {env_file_path}")
        print("📝 Copy the relevant settings to your .env file")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Interactive cloud storage setup"
    )
    parser.add_argument(
        '--provider',
        choices=['aws_s3', 'azure_blob', 'gcp_storage'],
        help="Set up specific provider only"
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        default=True,
        help="Run interactive setup (default)"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Create setup instance
    setup = CloudStorageSetup(dry_run=args.dry_run, verbose=args.verbose)
    
    try:
        if args.interactive:
            results = await setup.setup_interactive()
        else:
            print("Non-interactive setup not implemented yet")
            return
        
        print("\n🎉 Setup completed!")
        print("Next steps:")
        print("1. Review the generated .env.cloud-storage file")
        print("2. Copy relevant settings to your .env file")
        print("3. Run: python validate_cloud_storage_config.py")
        print("4. Start your application with cloud storage enabled")
        
    except KeyboardInterrupt:
        print("\nSetup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Setup failed with error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())