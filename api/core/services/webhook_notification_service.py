"""
Webhook Notification Service

Handles sending webhook notifications for batch processing job completion.
Includes retry logic and timeout handling.
"""

import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import aiohttp

from core.models.models_per_tenant import BatchProcessingJob

logger = logging.getLogger(__name__)


class WebhookNotificationService:
    """
    Service for sending webhook notifications about batch job completion.
    
    Sends POST requests to configured webhook URLs with job status and results.
    Includes retry logic (up to 3 attempts) and 30-second timeout.
    """

    # Webhook configuration
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 30
    RETRY_DELAYS = [2, 4, 8]  # Exponential backoff in seconds

    def __init__(self):
        """Initialize the webhook notification service."""
        logger.info("WebhookNotificationService initialized")

    async def send_job_completion_notification(
        self,
        job: BatchProcessingJob
    ) -> Dict[str, Any]:
        """
        Send webhook notification for job completion.
        
        Sends POST request to webhook_url with job status and export URL.
        Includes job_id, status, total_files, successful_files, failed_files,
        and export_file_url in the payload.
        
        Retries up to 3 times on failure with exponential backoff.
        Uses 30-second timeout for each request.
        
        Args:
            job: BatchProcessingJob instance
            
        Returns:
            Dictionary with notification delivery status
        """
        if not job.webhook_url:
            logger.debug(f"No webhook URL configured for job {job.job_id}")
            return {
                "job_id": job.job_id,
                "status": "skipped",
                "reason": "No webhook URL configured"
            }
        
        webhook_url = job.webhook_url
        
        logger.info(
            f"Sending webhook notification for job {job.job_id} to {webhook_url}"
        )
        
        # Build webhook payload
        payload = self._build_webhook_payload(job)
        
        # Attempt to send webhook with retries
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                logger.info(
                    f"Webhook attempt {attempt + 1}/{self.MAX_RETRIES} "
                    f"for job {job.job_id}"
                )
                
                result = await self._send_webhook_request(
                    webhook_url=webhook_url,
                    payload=payload,
                    attempt=attempt + 1
                )
                
                # Success - log and return
                logger.info(
                    f"Webhook notification sent successfully for job {job.job_id} "
                    f"(attempt {attempt + 1}): status={result['status_code']}"
                )
                
                return {
                    "job_id": job.job_id,
                    "status": "delivered",
                    "webhook_url": webhook_url,
                    "attempt": attempt + 1,
                    "status_code": result["status_code"],
                    "response": result.get("response"),
                    "delivered_at": datetime.now(timezone.utc).isoformat()
                }
                
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Webhook attempt {attempt + 1} failed for job {job.job_id}: {e}"
                )
                
                # If not the last attempt, wait before retrying
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAYS[attempt]
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        error_msg = f"Webhook delivery failed after {self.MAX_RETRIES} attempts: {str(last_error)}"
        logger.error(f"Job {job.job_id}: {error_msg}")
        
        return {
            "job_id": job.job_id,
            "status": "failed",
            "webhook_url": webhook_url,
            "attempts": self.MAX_RETRIES,
            "error": str(last_error),
            "failed_at": datetime.now(timezone.utc).isoformat()
        }

    def _build_webhook_payload(self, job: BatchProcessingJob) -> Dict[str, Any]:
        """
        Build webhook payload from job data.
        
        Args:
            job: BatchProcessingJob instance
            
        Returns:
            Dictionary with webhook payload
        """
        payload = {
            "job_id": job.job_id,
            "status": job.status,
            "total_files": job.total_files,
            "successful_files": job.successful_files,
            "failed_files": job.failed_files,
            "processed_files": job.processed_files,
            "progress_percentage": job.progress_percentage,
            "export_file_url": job.export_file_url,
            "export_completed_at": (
                job.export_completed_at.isoformat()
                if job.export_completed_at
                else None
            ),
            "created_at": (
                job.created_at.isoformat()
                if job.created_at
                else None
            ),
            "completed_at": (
                job.completed_at.isoformat()
                if job.completed_at
                else None
            ),
            "tenant_id": job.tenant_id,
            "document_types": job.document_types,
            "export_destination_type": job.export_destination_type,
            "webhook_sent_at": datetime.now(timezone.utc).isoformat()
        }
        
        return payload

    async def _send_webhook_request(
        self,
        webhook_url: str,
        payload: Dict[str, Any],
        attempt: int
    ) -> Dict[str, Any]:
        """
        Send HTTP POST request to webhook URL.
        
        Args:
            webhook_url: Target webhook URL
            payload: JSON payload to send
            attempt: Current attempt number (for logging)
            
        Returns:
            Dictionary with response status and data
            
        Raises:
            Exception: If request fails or times out
        """
        timeout = aiohttp.ClientTimeout(total=self.TIMEOUT_SECONDS)
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "BatchProcessingWebhook/1.0",
            "X-Webhook-Attempt": str(attempt)
        }
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    headers=headers
                ) as response:
                    status_code = response.status
                    
                    # Try to read response body
                    try:
                        response_text = await response.text()
                        
                        # Try to parse as JSON
                        try:
                            response_data = json.loads(response_text)
                        except json.JSONDecodeError:
                            response_data = response_text
                    except Exception as e:
                        logger.warning(f"Failed to read response body: {e}")
                        response_data = None
                    
                    # Check if request was successful (2xx status code)
                    if 200 <= status_code < 300:
                        return {
                            "status_code": status_code,
                            "response": response_data,
                            "success": True
                        }
                    else:
                        # Non-2xx status code is considered a failure
                        raise Exception(
                            f"Webhook returned status {status_code}: {response_data}"
                        )
        
        except asyncio.TimeoutError:
            raise Exception(
                f"Webhook request timed out after {self.TIMEOUT_SECONDS} seconds"
            )
        except aiohttp.ClientError as e:
            raise Exception(f"Webhook request failed: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error sending webhook: {str(e)}")

    async def test_webhook_url(
        self,
        webhook_url: str,
        test_payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Test a webhook URL with a sample payload.
        
        Useful for validating webhook configuration before using it in production.
        
        Args:
            webhook_url: Webhook URL to test
            test_payload: Optional custom test payload (uses default if None)
            
        Returns:
            Dictionary with test results
        """
        if test_payload is None:
            test_payload = {
                "job_id": "test-job-id",
                "status": "completed",
                "total_files": 10,
                "successful_files": 10,
                "failed_files": 0,
                "processed_files": 10,
                "progress_percentage": 100.0,
                "export_file_url": "https://example.com/export.csv",
                "test": True,
                "webhook_sent_at": datetime.now(timezone.utc).isoformat()
            }
        
        logger.info(f"Testing webhook URL: {webhook_url}")
        
        try:
            result = await self._send_webhook_request(
                webhook_url=webhook_url,
                payload=test_payload,
                attempt=1
            )
            
            logger.info(
                f"Webhook test successful: status={result['status_code']}"
            )
            
            return {
                "status": "success",
                "webhook_url": webhook_url,
                "status_code": result["status_code"],
                "response": result.get("response"),
                "tested_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Webhook test failed: {e}")
            
            return {
                "status": "failed",
                "webhook_url": webhook_url,
                "error": str(e),
                "tested_at": datetime.now(timezone.utc).isoformat()
            }

    def get_retry_config(self) -> Dict[str, Any]:
        """
        Get current retry configuration.
        
        Returns:
            Dictionary with retry settings
        """
        return {
            "max_retries": self.MAX_RETRIES,
            "timeout_seconds": self.TIMEOUT_SECONDS,
            "retry_delays": self.RETRY_DELAYS
        }
