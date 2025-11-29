"""
Rate Limiter Service

Implements per-API-client rate limiting for batch processing endpoints.
Uses in-memory cache with thread-safe operations.
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class RateLimiterService:
    """
    Rate limiter service for API clients.
    
    Tracks request counts per API client across different time windows:
    - Per minute
    - Per hour
    - Per day
    
    Uses in-memory storage with automatic cleanup of expired entries.
    """
    
    def __init__(self):
        """Initialize rate limiter with in-memory storage."""
        # Storage format: {api_client_id: {window: [(timestamp, count)]}}
        self._storage: Dict[str, Dict[str, list]] = defaultdict(lambda: {
            'minute': [],
            'hour': [],
            'day': []
        })
        self._lock = Lock()
        
        # Window durations in seconds
        self._windows = {
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }
        
        logger.info("Rate limiter service initialized with in-memory storage")
    
    def check_rate_limit(
        self,
        api_client_id: str,
        rate_limit_per_minute: int,
        rate_limit_per_hour: int,
        rate_limit_per_day: int,
        custom_quotas: Optional[Dict] = None
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Check if API client has exceeded rate limits.
        
        Args:
            api_client_id: Unique identifier for the API client
            rate_limit_per_minute: Maximum requests per minute
            rate_limit_per_hour: Maximum requests per hour
            rate_limit_per_day: Maximum requests per day
            custom_quotas: Optional custom quota overrides
            
        Returns:
            Tuple of (allowed, error_message, retry_after_seconds)
            - allowed: True if request is allowed, False if rate limit exceeded
            - error_message: Description of which limit was exceeded (if any)
            - retry_after_seconds: Seconds to wait before retrying (if limited)
        """
        # Apply custom quotas if provided
        if custom_quotas:
            if 'rate_limit_per_minute' in custom_quotas:
                rate_limit_per_minute = custom_quotas['rate_limit_per_minute']
                logger.info(
                    f"Applying custom rate_limit_per_minute for {api_client_id}: "
                    f"{rate_limit_per_minute}"
                )
            if 'rate_limit_per_hour' in custom_quotas:
                rate_limit_per_hour = custom_quotas['rate_limit_per_hour']
                logger.info(
                    f"Applying custom rate_limit_per_hour for {api_client_id}: "
                    f"{rate_limit_per_hour}"
                )
            if 'rate_limit_per_day' in custom_quotas:
                rate_limit_per_day = custom_quotas['rate_limit_per_day']
                logger.info(
                    f"Applying custom rate_limit_per_day for {api_client_id}: "
                    f"{rate_limit_per_day}"
                )
        
        with self._lock:
            current_time = time.time()
            
            # Clean up expired entries
            self._cleanup_expired_entries(api_client_id, current_time)
            
            # Get current counts for each window
            counts = self._get_current_counts(api_client_id, current_time)
            
            # Check each rate limit
            if counts['minute'] >= rate_limit_per_minute:
                retry_after = self._calculate_retry_after(
                    api_client_id, 'minute', current_time
                )
                logger.warning(
                    f"Rate limit exceeded for {api_client_id}: "
                    f"{counts['minute']}/{rate_limit_per_minute} per minute"
                )
                return (
                    False,
                    f"Rate limit exceeded: {counts['minute']}/{rate_limit_per_minute} requests per minute",
                    retry_after
                )
            
            if counts['hour'] >= rate_limit_per_hour:
                retry_after = self._calculate_retry_after(
                    api_client_id, 'hour', current_time
                )
                logger.warning(
                    f"Rate limit exceeded for {api_client_id}: "
                    f"{counts['hour']}/{rate_limit_per_hour} per hour"
                )
                return (
                    False,
                    f"Rate limit exceeded: {counts['hour']}/{rate_limit_per_hour} requests per hour",
                    retry_after
                )
            
            if counts['day'] >= rate_limit_per_day:
                retry_after = self._calculate_retry_after(
                    api_client_id, 'day', current_time
                )
                logger.warning(
                    f"Rate limit exceeded for {api_client_id}: "
                    f"{counts['day']}/{rate_limit_per_day} per day"
                )
                return (
                    False,
                    f"Rate limit exceeded: {counts['day']}/{rate_limit_per_day} requests per day",
                    retry_after
                )
            
            # All checks passed - increment counters
            self._increment_counters(api_client_id, current_time)
            
            logger.debug(
                f"Rate limit check passed for {api_client_id}: "
                f"minute={counts['minute']}/{rate_limit_per_minute}, "
                f"hour={counts['hour']}/{rate_limit_per_hour}, "
                f"day={counts['day']}/{rate_limit_per_day}"
            )
            
            return (True, None, None)
    
    def _cleanup_expired_entries(self, api_client_id: str, current_time: float):
        """
        Remove expired entries from storage.
        
        Args:
            api_client_id: API client identifier
            current_time: Current timestamp
        """
        if api_client_id not in self._storage:
            return
        
        for window, duration in self._windows.items():
            cutoff_time = current_time - duration
            # Keep only entries within the window
            self._storage[api_client_id][window] = [
                (ts, count) for ts, count in self._storage[api_client_id][window]
                if ts > cutoff_time
            ]
    
    def _get_current_counts(
        self,
        api_client_id: str,
        current_time: float
    ) -> Dict[str, int]:
        """
        Get current request counts for all windows.
        
        Args:
            api_client_id: API client identifier
            current_time: Current timestamp
            
        Returns:
            Dictionary with counts for each window
        """
        counts = {}
        
        for window, duration in self._windows.items():
            cutoff_time = current_time - duration
            count = sum(
                c for ts, c in self._storage[api_client_id][window]
                if ts > cutoff_time
            )
            counts[window] = count
        
        return counts
    
    def _increment_counters(self, api_client_id: str, current_time: float):
        """
        Increment request counters for all windows.
        
        Args:
            api_client_id: API client identifier
            current_time: Current timestamp
        """
        for window in self._windows.keys():
            self._storage[api_client_id][window].append((current_time, 1))
    
    def _calculate_retry_after(
        self,
        api_client_id: str,
        window: str,
        current_time: float
    ) -> int:
        """
        Calculate seconds until rate limit resets.
        
        Args:
            api_client_id: API client identifier
            window: Time window that was exceeded
            current_time: Current timestamp
            
        Returns:
            Seconds to wait before retrying
        """
        if api_client_id not in self._storage:
            return self._windows[window]
        
        entries = self._storage[api_client_id][window]
        if not entries:
            return self._windows[window]
        
        # Find the oldest entry in the window
        oldest_timestamp = min(ts for ts, _ in entries)
        window_duration = self._windows[window]
        
        # Calculate when the oldest entry will expire
        expires_at = oldest_timestamp + window_duration
        retry_after = max(1, int(expires_at - current_time))
        
        return retry_after
    
    def get_current_usage(
        self,
        api_client_id: str
    ) -> Dict[str, int]:
        """
        Get current usage counts for an API client.
        
        Useful for monitoring and debugging.
        
        Args:
            api_client_id: API client identifier
            
        Returns:
            Dictionary with current counts for each window
        """
        with self._lock:
            current_time = time.time()
            self._cleanup_expired_entries(api_client_id, current_time)
            return self._get_current_counts(api_client_id, current_time)
    
    def reset_limits(self, api_client_id: str):
        """
        Reset all rate limits for an API client.
        
        Useful for testing or administrative purposes.
        
        Args:
            api_client_id: API client identifier
        """
        with self._lock:
            if api_client_id in self._storage:
                del self._storage[api_client_id]
                logger.info(f"Reset rate limits for {api_client_id}")
    
    def check_concurrent_jobs(
        self,
        api_client_id: str,
        db: Session,
        max_concurrent_jobs: int = 5,
        custom_quotas: Optional[Dict] = None
    ) -> Tuple[bool, Optional[str], int]:
        """
        Check if API client has exceeded concurrent job limits.
        
        Args:
            api_client_id: Unique identifier for the API client
            db: Database session for querying active jobs
            max_concurrent_jobs: Maximum concurrent jobs allowed (default: 5)
            custom_quotas: Optional custom quota overrides
            
        Returns:
            Tuple of (allowed, error_message, active_job_count)
            - allowed: True if new job is allowed, False if limit exceeded
            - error_message: Description of limit exceeded (if any)
            - active_job_count: Current number of active jobs
        """
        from core.models.models_per_tenant import BatchProcessingJob
        
        # Apply custom quota if provided
        if custom_quotas and 'max_concurrent_jobs' in custom_quotas:
            max_concurrent_jobs = custom_quotas['max_concurrent_jobs']
            logger.info(
                f"Applying custom max_concurrent_jobs for {api_client_id}: "
                f"{max_concurrent_jobs}"
            )
        
        # Count active jobs (pending or processing) for this API client
        active_job_count = db.query(BatchProcessingJob).filter(
            BatchProcessingJob.api_client_id == api_client_id,
            BatchProcessingJob.status.in_(['pending', 'processing'])
        ).count()
        
        if active_job_count >= max_concurrent_jobs:
            logger.warning(
                f"Concurrent job limit exceeded for {api_client_id}: "
                f"{active_job_count}/{max_concurrent_jobs} active jobs"
            )
            return (
                False,
                f"Concurrent job limit exceeded: {active_job_count}/{max_concurrent_jobs} active jobs. "
                f"Please wait for existing jobs to complete.",
                active_job_count
            )
        
        logger.debug(
            f"Concurrent job check passed for {api_client_id}: "
            f"{active_job_count}/{max_concurrent_jobs} active jobs"
        )
        
        return (True, None, active_job_count)


# Global rate limiter instance
_rate_limiter_instance: Optional[RateLimiterService] = None


def get_rate_limiter() -> RateLimiterService:
    """
    Get or create the global rate limiter instance.
    
    Returns:
        RateLimiterService instance
    """
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = RateLimiterService()
    return _rate_limiter_instance
