"""
Test script for Batch Completion Monitor and Webhook Notification services.

This script demonstrates and tests the batch completion monitoring functionality.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

from config import get_settings
from core.models.models_per_tenant import BatchProcessingJob, BatchFileProcessing
from core.services.batch_completion_monitor import BatchCompletionMonitor
from core.services.webhook_notification_service import WebhookNotificationService


async def test_webhook_service():
    """Test the webhook notification service."""
    print("\n=== Testing Webhook Notification Service ===\n")
    
    webhook_service = WebhookNotificationService()
    
    # Test webhook URL (using httpbin.org for testing)
    test_url = "https://httpbin.org/post"
    
    print(f"Testing webhook URL: {test_url}")
    result = await webhook_service.test_webhook_url(test_url)
    
    print(f"Test result: {result['status']}")
    if result['status'] == 'success':
        print(f"Status code: {result['status_code']}")
        print(f"Response: {result.get('response', {}).get('json', 'N/A')}")
    else:
        print(f"Error: {result.get('error')}")
    
    # Test retry configuration
    print(f"\nRetry configuration: {webhook_service.get_retry_config()}")


async def test_completion_monitor():
    """Test the batch completion monitor."""
    print("\n=== Testing Batch Completion Monitor ===\n")
    
    # Create database session factory
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create monitor instance
    monitor = BatchCompletionMonitor(SessionLocal)
    
    print(f"Monitor status: {monitor.get_status()}")
    
    # Test checking for completed jobs (should find none in test)
    print("\nChecking for completed jobs...")
    await monitor.check_for_completed_jobs()
    print("Check completed (no jobs found is expected in test environment)")


async def test_webhook_payload_building():
    """Test webhook payload building."""
    print("\n=== Testing Webhook Payload Building ===\n")
    
    # Create a mock job
    mock_job = BatchProcessingJob(
        job_id="test-job-123",
        tenant_id=1,
        user_id=1,
        api_client_id="test-client",
        document_types=["invoice", "expense"],
        total_files=10,
        processed_files=10,
        successful_files=9,
        failed_files=1,
        progress_percentage=100.0,
        status="completed",
        export_file_url="https://example.com/export.csv",
        export_destination_type="s3",
        webhook_url="https://httpbin.org/post",
        created_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        export_completed_at=datetime.now(timezone.utc)
    )
    
    webhook_service = WebhookNotificationService()
    payload = webhook_service._build_webhook_payload(mock_job)
    
    print("Generated webhook payload:")
    import json
    print(json.dumps(payload, indent=2, default=str))
    
    # Test sending notification with mock job
    print("\nSending test webhook notification...")
    result = await webhook_service.send_job_completion_notification(mock_job)
    
    print(f"Notification result: {result['status']}")
    if result['status'] == 'delivered':
        print(f"Delivered on attempt: {result['attempt']}")
        print(f"Status code: {result['status_code']}")
    else:
        print(f"Error: {result.get('error', 'Unknown')}")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("Batch Completion Monitor & Webhook Notification Tests")
    print("=" * 60)
    
    try:
        # Test webhook service
        await test_webhook_service()
        
        # Test webhook payload building
        await test_webhook_payload_building()
        
        # Test completion monitor
        await test_completion_monitor()
        
        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
