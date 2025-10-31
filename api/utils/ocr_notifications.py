"""
OCR Processing Notifications

This module provides user notification utilities for OCR processing operations,
including notifications for extended processing times and status updates.
"""

import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class OCRNotificationType(Enum):
    """Types of OCR notifications."""
    PROCESSING_STARTED = "processing_started"
    EXTENDED_PROCESSING = "extended_processing"
    PROCESSING_COMPLETED = "processing_completed"
    PROCESSING_FAILED = "processing_failed"
    OCR_FALLBACK_TRIGGERED = "ocr_fallback_triggered"


class OCRNotificationManager:
    """
    Manager for OCR processing notifications.
    
    Provides user feedback for OCR operations including extended processing times,
    fallback notifications, and completion status.
    """
    
    def __init__(self):
        """Initialize the notification manager."""
        self.notifications = {}
    
    def notify_processing_started(
        self,
        file_path: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        Notify that OCR processing has started.
        
        Args:
            file_path: Path to the file being processed
            user_id: User ID (optional)
            session_id: Session ID (optional)
        """
        message = f"Starting document processing for {self._get_filename(file_path)}"
        self._send_notification(
            OCRNotificationType.PROCESSING_STARTED,
            message,
            user_id=user_id,
            session_id=session_id,
            details={"file_path": file_path}
        )
    
    def notify_extended_processing(
        self,
        file_path: str,
        estimated_time: Optional[int] = None,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        Notify that processing is taking longer than expected.
        
        Args:
            file_path: Path to the file being processed
            estimated_time: Estimated remaining time in seconds
            user_id: User ID (optional)
            session_id: Session ID (optional)
        """
        filename = self._get_filename(file_path)
        if estimated_time:
            message = f"Document processing for {filename} is taking longer than expected. Estimated time remaining: {estimated_time // 60} minutes."
        else:
            message = f"Document processing for {filename} is taking longer than expected due to OCR requirements. Please wait..."
        
        self._send_notification(
            OCRNotificationType.EXTENDED_PROCESSING,
            message,
            user_id=user_id,
            session_id=session_id,
            details={
                "file_path": file_path,
                "estimated_time": estimated_time
            }
        )
    
    def notify_ocr_fallback_triggered(
        self,
        file_path: str,
        reason: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        Notify that OCR fallback has been triggered.
        
        Args:
            file_path: Path to the file being processed
            reason: Reason for OCR fallback
            user_id: User ID (optional)
            session_id: Session ID (optional)
        """
        filename = self._get_filename(file_path)
        message = f"Using advanced OCR processing for {filename}. This may take a few minutes for scanned documents."
        
        self._send_notification(
            OCRNotificationType.OCR_FALLBACK_TRIGGERED,
            message,
            user_id=user_id,
            session_id=session_id,
            details={
                "file_path": file_path,
                "reason": reason
            }
        )
    
    def notify_processing_completed(
        self,
        file_path: str,
        transaction_count: int,
        processing_time: float,
        extraction_method: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        Notify that processing has completed successfully.
        
        Args:
            file_path: Path to the processed file
            transaction_count: Number of transactions extracted
            processing_time: Total processing time in seconds
            extraction_method: Method used for extraction ("pdf_loader" or "ocr")
            user_id: User ID (optional)
            session_id: Session ID (optional)
        """
        filename = self._get_filename(file_path)
        method_text = "OCR processing" if extraction_method == "ocr" else "standard processing"
        message = f"Successfully processed {filename} using {method_text}. Found {transaction_count} transactions in {processing_time:.1f} seconds."
        
        self._send_notification(
            OCRNotificationType.PROCESSING_COMPLETED,
            message,
            user_id=user_id,
            session_id=session_id,
            details={
                "file_path": file_path,
                "transaction_count": transaction_count,
                "processing_time": processing_time,
                "extraction_method": extraction_method
            }
        )
    
    def notify_processing_failed(
        self,
        file_path: str,
        error_message: str,
        is_retryable: bool = False,
        retry_delay: Optional[int] = None,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        Notify that processing has failed.
        
        Args:
            file_path: Path to the file that failed processing
            error_message: Error message
            is_retryable: Whether the error is retryable
            retry_delay: Suggested retry delay in seconds
            user_id: User ID (optional)
            session_id: Session ID (optional)
        """
        filename = self._get_filename(file_path)
        
        if is_retryable and retry_delay:
            message = f"Processing failed for {filename}: {error_message}. Will retry in {retry_delay} seconds."
        elif is_retryable:
            message = f"Processing temporarily failed for {filename}: {error_message}. Please try again later."
        else:
            message = f"Processing failed for {filename}: {error_message}. Please check the file and try again."
        
        self._send_notification(
            OCRNotificationType.PROCESSING_FAILED,
            message,
            user_id=user_id,
            session_id=session_id,
            details={
                "file_path": file_path,
                "error_message": error_message,
                "is_retryable": is_retryable,
                "retry_delay": retry_delay
            }
        )
    
    def _send_notification(
        self,
        notification_type: OCRNotificationType,
        message: str,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send a notification to the user.
        
        Args:
            notification_type: Type of notification
            message: Notification message
            user_id: User ID (optional)
            session_id: Session ID (optional)
            details: Additional notification details
        """
        # For now, just log the notification
        # In a real implementation, this could send WebSocket messages,
        # email notifications, or store in a notification queue
        
        logger.info(
            f"OCR Notification [{notification_type.value}]: {message}",
            extra={
                "notification_type": notification_type.value,
                "user_id": user_id,
                "session_id": session_id,
                "details": details or {}
            }
        )
        
        # Store notification for potential retrieval
        notification_key = f"{user_id or 'anonymous'}_{session_id or 'no_session'}"
        if notification_key not in self.notifications:
            self.notifications[notification_key] = []
        
        self.notifications[notification_key].append({
            "type": notification_type.value,
            "message": message,
            "timestamp": self._get_current_timestamp(),
            "details": details or {}
        })
        
        # Keep only the last 10 notifications per user/session
        self.notifications[notification_key] = self.notifications[notification_key][-10:]
    
    def get_notifications(
        self,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> list:
        """
        Get notifications for a user/session.
        
        Args:
            user_id: User ID (optional)
            session_id: Session ID (optional)
            
        Returns:
            List of notifications
        """
        notification_key = f"{user_id or 'anonymous'}_{session_id or 'no_session'}"
        return self.notifications.get(notification_key, [])
    
    def clear_notifications(
        self,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        Clear notifications for a user/session.
        
        Args:
            user_id: User ID (optional)
            session_id: Session ID (optional)
        """
        notification_key = f"{user_id or 'anonymous'}_{session_id or 'no_session'}"
        if notification_key in self.notifications:
            del self.notifications[notification_key]
    
    def _get_filename(self, file_path: str) -> str:
        """Extract filename from file path."""
        from pathlib import Path
        return Path(file_path).name
    
    def _get_current_timestamp(self) -> str:
        """Get current timestamp as ISO string."""
        from datetime import datetime
        return datetime.utcnow().isoformat()


# Global notification manager instance
ocr_notification_manager = OCRNotificationManager()


# Convenience functions
def notify_ocr_processing_started(file_path: str, user_id: Optional[int] = None, session_id: Optional[str] = None):
    """Notify that OCR processing has started."""
    ocr_notification_manager.notify_processing_started(file_path, user_id, session_id)


def notify_ocr_extended_processing(file_path: str, estimated_time: Optional[int] = None, user_id: Optional[int] = None, session_id: Optional[str] = None):
    """Notify about extended OCR processing time."""
    ocr_notification_manager.notify_extended_processing(file_path, estimated_time, user_id, session_id)


def notify_ocr_fallback_triggered(file_path: str, reason: str, user_id: Optional[int] = None, session_id: Optional[str] = None):
    """Notify that OCR fallback has been triggered."""
    ocr_notification_manager.notify_ocr_fallback_triggered(file_path, reason, user_id, session_id)


def notify_ocr_processing_completed(file_path: str, transaction_count: int, processing_time: float, extraction_method: str, user_id: Optional[int] = None, session_id: Optional[str] = None):
    """Notify that OCR processing has completed."""
    ocr_notification_manager.notify_processing_completed(file_path, transaction_count, processing_time, extraction_method, user_id, session_id)


def notify_ocr_processing_failed(file_path: str, error_message: str, is_retryable: bool = False, retry_delay: Optional[int] = None, user_id: Optional[int] = None, session_id: Optional[str] = None):
    """Notify that OCR processing has failed."""
    ocr_notification_manager.notify_processing_failed(file_path, error_message, is_retryable, retry_delay, user_id, session_id)