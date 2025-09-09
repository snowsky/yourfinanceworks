"""
Report Progress Tracking Service

This service provides progress tracking capabilities for long-running report generation,
including real-time progress updates, status monitoring, and cancellation support.
"""

import asyncio
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor, Future


class ProgressStatus(Enum):
    """Progress status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProgressStage(Enum):
    """Progress stages for report generation"""
    INITIALIZING = "initializing"
    VALIDATING = "validating"
    QUERYING = "querying"
    PROCESSING = "processing"
    FORMATTING = "formatting"
    EXPORTING = "exporting"
    FINALIZING = "finalizing"


@dataclass
class ProgressUpdate:
    """Progress update information"""
    stage: ProgressStage
    percentage: float
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'stage': self.stage.value,
            'percentage': self.percentage,
            'message': self.message,
            'details': self.details or {},
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class ProgressTracker:
    """Progress tracker for a single report generation task"""
    task_id: str
    user_id: Optional[int]
    report_type: str
    status: ProgressStatus = ProgressStatus.PENDING
    current_stage: ProgressStage = ProgressStage.INITIALIZING
    overall_progress: float = 0.0
    stage_progress: float = 0.0
    message: str = "Initializing..."
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    updates: List[ProgressUpdate] = field(default_factory=list)
    cancellation_requested: bool = False
    result_data: Optional[Any] = None
    
    def update_progress(
        self,
        stage: Optional[ProgressStage] = None,
        percentage: Optional[float] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update progress information"""
        if stage is not None:
            self.current_stage = stage
        
        if percentage is not None:
            self.stage_progress = max(0.0, min(100.0, percentage))
            # Update overall progress based on stage
            self._update_overall_progress()
        
        if message is not None:
            self.message = message
        
        # Create progress update
        update = ProgressUpdate(
            stage=self.current_stage,
            percentage=self.overall_progress,
            message=self.message,
            details=details
        )
        
        self.updates.append(update)
        
        # Keep only recent updates (last 50)
        if len(self.updates) > 50:
            self.updates = self.updates[-50:]
    
    def _update_overall_progress(self) -> None:
        """Update overall progress based on current stage and stage progress"""
        stage_weights = {
            ProgressStage.INITIALIZING: (0, 5),
            ProgressStage.VALIDATING: (5, 10),
            ProgressStage.QUERYING: (10, 40),
            ProgressStage.PROCESSING: (40, 70),
            ProgressStage.FORMATTING: (70, 85),
            ProgressStage.EXPORTING: (85, 95),
            ProgressStage.FINALIZING: (95, 100)
        }
        
        if self.current_stage in stage_weights:
            start_pct, end_pct = stage_weights[self.current_stage]
            stage_contribution = (self.stage_progress / 100.0) * (end_pct - start_pct)
            self.overall_progress = start_pct + stage_contribution
    
    def mark_started(self) -> None:
        """Mark the task as started"""
        self.status = ProgressStatus.RUNNING
        self.started_at = datetime.now()
        self.update_progress(message="Report generation started")
    
    def mark_completed(self, result_data: Optional[Any] = None) -> None:
        """Mark the task as completed"""
        self.status = ProgressStatus.COMPLETED
        self.completed_at = datetime.now()
        self.overall_progress = 100.0
        self.result_data = result_data
        self.update_progress(
            stage=ProgressStage.FINALIZING,
            percentage=100.0,
            message="Report generation completed successfully"
        )
    
    def mark_failed(self, error_message: str) -> None:
        """Mark the task as failed"""
        self.status = ProgressStatus.FAILED
        self.completed_at = datetime.now()
        self.error_message = error_message
        self.update_progress(message=f"Report generation failed: {error_message}")
    
    def mark_cancelled(self) -> None:
        """Mark the task as cancelled"""
        self.status = ProgressStatus.CANCELLED
        self.completed_at = datetime.now()
        self.update_progress(message="Report generation cancelled")
    
    def request_cancellation(self) -> None:
        """Request cancellation of the task"""
        self.cancellation_requested = True
        self.update_progress(message="Cancellation requested...")
    
    def is_active(self) -> bool:
        """Check if the task is currently active"""
        return self.status in [ProgressStatus.PENDING, ProgressStatus.RUNNING]
    
    def get_duration(self) -> Optional[timedelta]:
        """Get the duration of the task"""
        if self.started_at is None:
            return None
        
        end_time = self.completed_at or datetime.now()
        return end_time - self.started_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        duration = self.get_duration()
        
        return {
            'task_id': self.task_id,
            'user_id': self.user_id,
            'report_type': self.report_type,
            'status': self.status.value,
            'current_stage': self.current_stage.value,
            'overall_progress': self.overall_progress,
            'stage_progress': self.stage_progress,
            'message': self.message,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'estimated_completion': self.estimated_completion.isoformat() if self.estimated_completion else None,
            'duration_seconds': duration.total_seconds() if duration else None,
            'cancellation_requested': self.cancellation_requested,
            'latest_updates': [update.to_dict() for update in self.updates[-5:]]  # Last 5 updates
        }


class ReportProgressService:
    """
    Service for tracking progress of long-running report generation tasks.
    Provides real-time progress updates, cancellation support, and task management.
    """
    
    def __init__(self, max_concurrent_tasks: int = 10):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.logger = logging.getLogger(__name__)
        
        # Task storage
        self._tasks: Dict[str, ProgressTracker] = {}
        self._task_lock = threading.RLock()
        
        # Thread pool for background tasks
        self._executor = ThreadPoolExecutor(max_workers=max_concurrent_tasks)
        self._futures: Dict[str, Future] = {}
        
        # Cleanup thread
        self._cleanup_thread = None
        self._shutdown_event = threading.Event()
        
        self._start_cleanup_thread()
        
        self.logger.info(f"Initialized ReportProgressService with {max_concurrent_tasks} max concurrent tasks")
    
    def create_task(
        self,
        report_type: str,
        user_id: Optional[int] = None,
        task_id: Optional[str] = None
    ) -> str:
        """
        Create a new progress tracking task.
        
        Args:
            report_type: Type of report being generated
            user_id: ID of the user requesting the report
            task_id: Optional custom task ID
            
        Returns:
            Task ID for tracking progress
        """
        if task_id is None:
            task_id = str(uuid.uuid4())
        
        with self._task_lock:
            tracker = ProgressTracker(
                task_id=task_id,
                user_id=user_id,
                report_type=report_type
            )
            
            self._tasks[task_id] = tracker
            
            self.logger.debug(f"Created progress task {task_id} for report type {report_type}")
            
            return task_id
    
    def get_task(self, task_id: str) -> Optional[ProgressTracker]:
        """
        Get a progress tracker by task ID.
        
        Args:
            task_id: Task ID to retrieve
            
        Returns:
            ProgressTracker if found, None otherwise
        """
        with self._task_lock:
            return self._tasks.get(task_id)
    
    def update_task_progress(
        self,
        task_id: str,
        stage: Optional[ProgressStage] = None,
        percentage: Optional[float] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update progress for a task.
        
        Args:
            task_id: Task ID to update
            stage: Current stage of processing
            percentage: Progress percentage for current stage
            message: Progress message
            details: Additional details
            
        Returns:
            True if task was found and updated, False otherwise
        """
        with self._task_lock:
            tracker = self._tasks.get(task_id)
            if tracker is None:
                return False
            
            tracker.update_progress(stage, percentage, message, details)
            
            # Update estimated completion time
            if tracker.started_at and tracker.overall_progress > 0:
                elapsed = datetime.now() - tracker.started_at
                estimated_total = elapsed.total_seconds() * (100.0 / tracker.overall_progress)
                tracker.estimated_completion = tracker.started_at + timedelta(seconds=estimated_total)
            
            return True
    
    def start_task(self, task_id: str) -> bool:
        """
        Mark a task as started.
        
        Args:
            task_id: Task ID to start
            
        Returns:
            True if task was found and started, False otherwise
        """
        with self._task_lock:
            tracker = self._tasks.get(task_id)
            if tracker is None:
                return False
            
            tracker.mark_started()
            return True
    
    def complete_task(self, task_id: str, result_data: Optional[Any] = None) -> bool:
        """
        Mark a task as completed.
        
        Args:
            task_id: Task ID to complete
            result_data: Optional result data
            
        Returns:
            True if task was found and completed, False otherwise
        """
        with self._task_lock:
            tracker = self._tasks.get(task_id)
            if tracker is None:
                return False
            
            tracker.mark_completed(result_data)
            
            # Clean up future if exists
            future = self._futures.pop(task_id, None)
            if future and not future.done():
                future.cancel()
            
            return True
    
    def fail_task(self, task_id: str, error_message: str) -> bool:
        """
        Mark a task as failed.
        
        Args:
            task_id: Task ID to fail
            error_message: Error message
            
        Returns:
            True if task was found and failed, False otherwise
        """
        with self._task_lock:
            tracker = self._tasks.get(task_id)
            if tracker is None:
                return False
            
            tracker.mark_failed(error_message)
            
            # Clean up future if exists
            future = self._futures.pop(task_id, None)
            if future and not future.done():
                future.cancel()
            
            return True
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if task was found and cancelled, False otherwise
        """
        with self._task_lock:
            tracker = self._tasks.get(task_id)
            if tracker is None:
                return False
            
            tracker.request_cancellation()
            
            # Cancel the future if it exists
            future = self._futures.get(task_id)
            if future and not future.done():
                future.cancel()
                tracker.mark_cancelled()
            
            return True
    
    def is_cancellation_requested(self, task_id: str) -> bool:
        """
        Check if cancellation has been requested for a task.
        
        Args:
            task_id: Task ID to check
            
        Returns:
            True if cancellation was requested, False otherwise
        """
        with self._task_lock:
            tracker = self._tasks.get(task_id)
            return tracker.cancellation_requested if tracker else False
    
    def execute_with_progress(
        self,
        task_id: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Future:
        """
        Execute a function with progress tracking.
        
        Args:
            task_id: Task ID for progress tracking
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Future object for the execution
        """
        def wrapped_execution():
            try:
                self.start_task(task_id)
                result = func(task_id, *args, **kwargs)
                self.complete_task(task_id, result)
                return result
            except Exception as e:
                self.fail_task(task_id, str(e))
                raise
        
        future = self._executor.submit(wrapped_execution)
        self._futures[task_id] = future
        
        return future
    
    def get_user_tasks(self, user_id: int, active_only: bool = False) -> List[ProgressTracker]:
        """
        Get all tasks for a specific user.
        
        Args:
            user_id: User ID to get tasks for
            active_only: If True, only return active tasks
            
        Returns:
            List of progress trackers for the user
        """
        with self._task_lock:
            tasks = [
                tracker for tracker in self._tasks.values()
                if tracker.user_id == user_id
            ]
            
            if active_only:
                tasks = [task for task in tasks if task.is_active()]
            
            return sorted(tasks, key=lambda t: t.created_at, reverse=True)
    
    def get_all_tasks(self, active_only: bool = False) -> List[ProgressTracker]:
        """
        Get all tasks.
        
        Args:
            active_only: If True, only return active tasks
            
        Returns:
            List of all progress trackers
        """
        with self._task_lock:
            tasks = list(self._tasks.values())
            
            if active_only:
                tasks = [task for task in tasks if task.is_active()]
            
            return sorted(tasks, key=lambda t: t.created_at, reverse=True)
    
    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """
        Clean up old completed tasks.
        
        Args:
            max_age_hours: Maximum age in hours for completed tasks
            
        Returns:
            Number of tasks cleaned up
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        cleaned_count = 0
        
        with self._task_lock:
            tasks_to_remove = []
            
            for task_id, tracker in self._tasks.items():
                if (not tracker.is_active() and 
                    tracker.completed_at and 
                    tracker.completed_at < cutoff_time):
                    tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                del self._tasks[task_id]
                # Clean up future if exists
                self._futures.pop(task_id, None)
                cleaned_count += 1
        
        if cleaned_count > 0:
            self.logger.debug(f"Cleaned up {cleaned_count} old tasks")
        
        return cleaned_count
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get service statistics.
        
        Returns:
            Dictionary with service statistics
        """
        with self._task_lock:
            total_tasks = len(self._tasks)
            active_tasks = sum(1 for task in self._tasks.values() if task.is_active())
            completed_tasks = sum(1 for task in self._tasks.values() if task.status == ProgressStatus.COMPLETED)
            failed_tasks = sum(1 for task in self._tasks.values() if task.status == ProgressStatus.FAILED)
            cancelled_tasks = sum(1 for task in self._tasks.values() if task.status == ProgressStatus.CANCELLED)
            
            return {
                'total_tasks': total_tasks,
                'active_tasks': active_tasks,
                'completed_tasks': completed_tasks,
                'failed_tasks': failed_tasks,
                'cancelled_tasks': cancelled_tasks,
                'max_concurrent_tasks': self.max_concurrent_tasks,
                'executor_threads': self._executor._threads if hasattr(self._executor, '_threads') else 0
            }
    
    def _start_cleanup_thread(self) -> None:
        """Start the background cleanup thread"""
        def cleanup_worker():
            while not self._shutdown_event.wait(300):  # Check every 5 minutes
                try:
                    self.cleanup_old_tasks()
                except Exception as e:
                    self.logger.error(f"Error in cleanup thread: {e}")
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
    
    def shutdown(self) -> None:
        """Shutdown the service and clean up resources"""
        self.logger.info("Shutting down ReportProgressService")
        
        # Signal shutdown
        self._shutdown_event.set()
        
        # Cancel all active futures
        with self._task_lock:
            for future in self._futures.values():
                if not future.done():
                    future.cancel()
        
        # Shutdown executor
        self._executor.shutdown(wait=True)
        
        # Wait for cleanup thread
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)


# Global progress service instance
_progress_service: Optional[ReportProgressService] = None


def get_progress_service(max_concurrent_tasks: int = 10) -> ReportProgressService:
    """
    Get the global progress service instance.
    
    Args:
        max_concurrent_tasks: Maximum concurrent tasks (only used on first call)
        
    Returns:
        ReportProgressService instance
    """
    global _progress_service
    
    if _progress_service is None:
        _progress_service = ReportProgressService(max_concurrent_tasks)
    
    return _progress_service


def create_progress_callback(task_id: str) -> Callable:
    """
    Create a progress callback function for a task.
    
    Args:
        task_id: Task ID to update
        
    Returns:
        Callback function that can be used to update progress
    """
    progress_service = get_progress_service()
    
    def callback(percentage: float, message: str = None, details: Dict[str, Any] = None):
        progress_service.update_task_progress(
            task_id=task_id,
            percentage=percentage,
            message=message,
            details=details
        )
    
    return callback