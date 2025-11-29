#!/usr/bin/env python3
"""
Check cloud storage configuration in API and OCR worker containers.
This script helps diagnose why bank statements aren't appearing in S3.
"""

import os
import sys
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the API directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_environment_variables():
    """Check relevant environment variables for cloud storage."""
    logger.info("🔍 Checking Environment Variables...")
    
    env_vars = [
        "CLOUD_STORAGE_PRIMARY_PROVIDER",
        "CLOUD_STORAGE_ENABLED", 
        "AWS_S3_ENABLED",
        "AWS_S3_BUCKET_NAME",
        "AWS_S3_REGION",
        "AWS_S3_ACCESS_KEY_ID",
        "AWS_S3_SECRET_ACCESS_KEY",
        "CLOUD_STORAGE_FALLBACK_ENABLED",
        "STORAGE_AUTO_MIGRATION_ENABLED"
    ]
    
    for var in env_vars:
        value = os.getenv(var, "NOT SET")
        if "SECRET" in var or "KEY" in var:
            display_value = "***REDACTED***" if value != "NOT SET" else "NOT SET"
        else:
            display_value = value
        logger.info(f"  {var}: {display_value}")


def check_cloud_storage_config():
    """Check cloud storage configuration."""
    logger.info("⚙️ Checking Cloud Storage Configuration...")
    
    try:
        from commercial.cloud_storage.config import get_cloud_storage_config
        
        config = get_cloud_storage_config()
        
        logger.info(f"  Primary Provider: {config.PRIMARY_PROVIDER}")
        logger.info(f"  AWS S3 Enabled: {config.AWS_S3_ENABLED}")
        logger.info(f"  AWS S3 Bucket: {config.AWS_S3_BUCKET_NAME or 'NOT SET'}")
        logger.info(f"  AWS S3 Region: {config.AWS_S3_REGION}")
        logger.info(f"  Fallback Enabled: {config.FALLBACK_ENABLED}")
        logger.info(f"  Enabled Providers: {[p.value for p in config.get_enabled_providers()]}")
        
        return config
        
    except Exception as e:
        logger.error(f"❌ Failed to load cloud storage config: {e}")
        return None


def check_cloud_storage_service():
    """Check if cloud storage service is available."""
    logger.info("🔧 Checking Cloud Storage Service...")
    
    try:
        from commercial.cloud_storage.service import CloudStorageService
        from core.models.database import get_db
        from commercial.cloud_storage.config import get_cloud_storage_config
        
        # Get database session
        db = next(get_db())
        config = get_cloud_storage_config()
        
        # Initialize cloud storage service
        service = CloudStorageService(db, config)
        
        logger.info("✅ Cloud Storage Service initialized successfully")
        
        # Test service status
        status = service.get_service_status()
        logger.info(f"  Service Status: {status}")
        
        return service
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize cloud storage service: {e}")
        return None


def test_s3_connection():
    """Test S3 connection if configured."""
    logger.info("🌐 Testing S3 Connection...")
    
    try:
        from commercial.cloud_storage.config import get_cloud_storage_config, CloudStorageConfigurationManager
        from commercial.cloud_storage.config import StorageProvider
        
        config = get_cloud_storage_config()
        
        if not config.AWS_S3_ENABLED:
            logger.warning("⚠️ AWS S3 is not enabled")
            return False
        
        if not config.AWS_S3_BUCKET_NAME:
            logger.error("❌ AWS S3 bucket name not configured")
            return False
        
        # Test connection
        manager = CloudStorageConfigurationManager()
        s3_config = config.get_provider_config(StorageProvider.AWS_S3)
        
        result = manager.test_provider_connection(StorageProvider.AWS_S3, s3_config)
        
        if result["success"]:
            logger.info(f"✅ S3 Connection Test: {result['message']}")
            return True
        else:
            logger.error(f"❌ S3 Connection Test Failed: {result['error']}")
            return False
            
    except Exception as e:
        logger.error(f"❌ S3 connection test failed: {e}")
        return False


def check_bank_statement_processing():
    """Check bank statement processing configuration."""
    logger.info("🏦 Checking Bank Statement Processing...")
    
    try:
        # Check external API router
        logger.info("  Checking External API Router...")
        from core.routers.external_api import router
        logger.info("  ✅ External API router loaded")
        
        # Check OCR consumer worker
        logger.info("  Checking OCR Consumer Worker...")
        from workers.ocr_consumer import main
        logger.info("  ✅ OCR consumer worker loaded")
        
        # Check if cloud storage is used in bank statement processing
        import inspect
        from core.routers import external_api
        
        source = inspect.getsource(external_api.process_statement_pdf)
        if "CloudStorageService" in source:
            logger.info("  ✅ External API uses CloudStorageService")
        else:
            logger.warning("  ⚠️ External API may not use CloudStorageService")
        
        from workers import ocr_consumer
        worker_source = inspect.getsource(ocr_consumer)
        if "cloud_storage" in worker_source.lower():
            logger.info("  ✅ OCR worker references cloud storage")
        else:
            logger.warning("  ⚠️ OCR worker may not use cloud storage")
            
    except Exception as e:
        logger.error(f"❌ Failed to check bank statement processing: {e}")


def check_container_info():
    """Check container information."""
    logger.info("🐳 Checking Container Information...")
    
    # Check if running in container
    if os.path.exists("/.dockerenv"):
        logger.info("  ✅ Running in Docker container")
    else:
        logger.info("  ℹ️ Not running in Docker container")
    
    # Check hostname (container name)
    hostname = os.getenv("HOSTNAME", "unknown")
    logger.info(f"  Hostname: {hostname}")
    
    # Check if this is API or worker container
    if "api" in hostname.lower():
        logger.info("  📡 This appears to be the API container")
    elif "worker" in hostname.lower() or "ocr" in hostname.lower():
        logger.info("  ⚙️ This appears to be the OCR worker container")
    else:
        logger.info("  ❓ Container type unclear")


def diagnose_s3_issue():
    """Diagnose why files aren't appearing in S3."""
    logger.info("🔍 Diagnosing S3 Issue...")
    
    issues = []
    recommendations = []
    
    config = check_cloud_storage_config()
    if not config:
        issues.append("Cloud storage configuration failed to load")
        recommendations.append("Check environment variables and configuration files")
        return issues, recommendations
    
    # Check if S3 is enabled
    if not config.AWS_S3_ENABLED:
        issues.append("AWS S3 is not enabled")
        recommendations.append("Set AWS_S3_ENABLED=true in environment variables")
    
    # Check if S3 is primary provider
    if config.PRIMARY_PROVIDER != "aws_s3":
        issues.append(f"Primary provider is '{config.PRIMARY_PROVIDER}', not 'aws_s3'")
        recommendations.append("Set CLOUD_STORAGE_PRIMARY_PROVIDER=aws_s3")
    
    # Check S3 configuration
    if not config.AWS_S3_BUCKET_NAME:
        issues.append("S3 bucket name not configured")
        recommendations.append("Set AWS_S3_BUCKET_NAME environment variable")
    
    if not config.AWS_S3_ACCESS_KEY_ID:
        issues.append("S3 access key not configured")
        recommendations.append("Set AWS_S3_ACCESS_KEY_ID environment variable")
    
    if not config.AWS_S3_SECRET_ACCESS_KEY:
        issues.append("S3 secret key not configured")
        recommendations.append("Set AWS_S3_SECRET_ACCESS_KEY environment variable")
    
    # Test S3 connection
    if config.AWS_S3_ENABLED and config.AWS_S3_BUCKET_NAME:
        s3_works = test_s3_connection()
        if not s3_works:
            issues.append("S3 connection test failed")
            recommendations.append("Check S3 credentials and bucket permissions")
    
    return issues, recommendations


def main():
    """Main function to run all checks."""
    logger.info("=" * 60)
    logger.info("🔍 CLOUD STORAGE CONFIGURATION CHECKER")
    logger.info("=" * 60)
    
    check_container_info()
    logger.info("-" * 40)
    
    check_environment_variables()
    logger.info("-" * 40)
    
    check_cloud_storage_config()
    logger.info("-" * 40)
    
    check_cloud_storage_service()
    logger.info("-" * 40)
    
    check_bank_statement_processing()
    logger.info("-" * 40)
    
    # Diagnose issues
    issues, recommendations = diagnose_s3_issue()
    
    logger.info("=" * 60)
    logger.info("📋 DIAGNOSIS SUMMARY")
    logger.info("=" * 60)
    
    if issues:
        logger.error("❌ ISSUES FOUND:")
        for i, issue in enumerate(issues, 1):
            logger.error(f"  {i}. {issue}")
        
        logger.info("")
        logger.info("💡 RECOMMENDATIONS:")
        for i, rec in enumerate(recommendations, 1):
            logger.info(f"  {i}. {rec}")
    else:
        logger.info("✅ No configuration issues found!")
        logger.info("If files still aren't appearing in S3, check:")
        logger.info("  1. Application logs for upload errors")
        logger.info("  2. S3 bucket permissions and policies")
        logger.info("  3. Network connectivity to S3")
    
    logger.info("=" * 60)


if __name__ == "__main__":
    main()