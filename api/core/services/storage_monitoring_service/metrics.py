"""
Storage metrics mixin for StorageMonitoringService.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from core.models.models_per_tenant import StorageOperationLog
from sqlalchemy import desc

from ._shared import (
    StorageUsageMetrics,
    PerformanceMetrics,
    and_,
)

logger = logging.getLogger(__name__)


class StorageMetricsMixin:
    """Mixin providing metrics collection methods for StorageMonitoringService."""

    async def get_storage_usage_metrics(
        self,
        tenant_id: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, StorageUsageMetrics]:
        """
        Get storage usage metrics for tenants.

        Args:
            tenant_id: Specific tenant ID (None for all tenants)
            force_refresh: Force refresh of cached metrics

        Returns:
            Dictionary mapping tenant IDs to usage metrics
        """
        cache_key = tenant_id or "all_tenants"

        # Check cache first
        if not force_refresh and cache_key in self._usage_cache:
            cached_metrics = self._usage_cache[cache_key]
            if (datetime.now() - cached_metrics.last_updated).seconds < self._usage_cache_ttl:
                return {cached_metrics.tenant_id: cached_metrics} if tenant_id else self._usage_cache

        logger.info(f"Calculating storage usage metrics for tenant: {tenant_id or 'all'}")

        # Build query
        query = self.db.query(StorageOperationLog)
        if tenant_id:
            query = query.filter(StorageOperationLog.tenant_id == tenant_id)

        # Get successful upload operations (these represent stored files)
        upload_logs = query.filter(
            and_(
                StorageOperationLog.operation_type == "upload",
                StorageOperationLog.success == True
            )
        ).all()

        # Group by tenant
        tenant_metrics = {}
        tenant_data = defaultdict(list)

        for log in upload_logs:
            tenant_data[str(log.tenant_id)].append(log)

        for tid, logs in tenant_data.items():
            # Calculate metrics for this tenant
            total_files = len(logs)
            total_size_bytes = sum(log.file_size or 0 for log in logs)

            # Group by provider
            files_by_provider = defaultdict(int)
            size_by_provider = defaultdict(int)
            for log in logs:
                files_by_provider[log.provider] += 1
                size_by_provider[log.provider] += log.file_size or 0

            # Group by file type (based on content_type)
            files_by_type = defaultdict(int)
            size_by_type = defaultdict(int)
            for log in logs:
                content_type = log.content_type or "unknown"
                file_type = content_type.split('/')[0] if '/' in content_type else content_type
                files_by_type[file_type] += 1
                size_by_type[file_type] += log.file_size or 0

            # Calculate growth rate (files and bytes per day over last 30 days)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_logs = [log for log in logs if log.created_at >= thirty_days_ago]

            growth_rate_files_per_day = len(recent_logs) / 30 if recent_logs else 0
            growth_rate_bytes_per_day = sum(log.file_size or 0 for log in recent_logs) / 30

            # Create usage metrics
            usage_metrics = StorageUsageMetrics(
                tenant_id=tid,
                total_files=total_files,
                total_size_bytes=total_size_bytes,
                files_by_provider=dict(files_by_provider),
                size_by_provider=dict(size_by_provider),
                files_by_type=dict(files_by_type),
                size_by_type=dict(size_by_type),
                growth_rate_files_per_day=growth_rate_files_per_day,
                growth_rate_bytes_per_day=growth_rate_bytes_per_day,
                last_updated=datetime.now()
            )

            tenant_metrics[tid] = usage_metrics
            self._usage_cache[tid] = usage_metrics

            # Check for usage alerts
            await self._check_usage_alerts(usage_metrics)

        # Cache all tenants result if requested
        if not tenant_id:
            self._usage_cache["all_tenants"] = tenant_metrics

        return tenant_metrics

    async def get_performance_metrics(
        self,
        provider: Optional[str] = None,
        operation_type: Optional[str] = None,
        hours: int = 24,
        force_refresh: bool = False
    ) -> List[PerformanceMetrics]:
        """
        Get performance metrics for storage operations.

        Args:
            provider: Filter by specific provider
            operation_type: Filter by operation type (upload, download, delete)
            hours: Number of hours to analyze
            force_refresh: Force refresh of cached metrics

        Returns:
            List of performance metrics
        """
        cache_key = f"{provider or 'all'}_{operation_type or 'all'}_{hours}h"

        # Check cache first
        if not force_refresh and cache_key in self._performance_cache:
            cached_time = getattr(self._performance_cache[cache_key], 'cached_at', datetime.min)
            if (datetime.now() - cached_time).seconds < self._performance_cache_ttl:
                return [self._performance_cache[cache_key]]

        logger.info(f"Calculating performance metrics for provider: {provider or 'all'}, operation: {operation_type or 'all'}")

        start_time = datetime.now() - timedelta(hours=hours)

        # Build query
        query = self.db.query(StorageOperationLog).filter(
            StorageOperationLog.created_at >= start_time
        )

        if provider:
            query = query.filter(StorageOperationLog.provider == provider)
        if operation_type:
            query = query.filter(StorageOperationLog.operation_type == operation_type)

        logs = query.all()

        if not logs:
            return []

        # Group by provider and operation type
        grouped_logs = defaultdict(list)
        for log in logs:
            key = (log.provider, log.operation_type)
            grouped_logs[key].append(log)

        performance_metrics = []

        for (prov, op_type), group_logs in grouped_logs.items():
            # Calculate latency metrics
            latencies = [log.duration_ms for log in group_logs if log.duration_ms is not None]

            if latencies:
                latencies.sort()
                avg_latency = sum(latencies) / len(latencies)
                p95_index = int(len(latencies) * 0.95)
                p99_index = int(len(latencies) * 0.99)
                p95_latency = latencies[p95_index] if p95_index < len(latencies) else latencies[-1]
                p99_latency = latencies[p99_index] if p99_index < len(latencies) else latencies[-1]
            else:
                avg_latency = p95_latency = p99_latency = 0.0

            # Calculate success rate and error rate
            total_ops = len(group_logs)
            successful_ops = sum(1 for log in group_logs if log.success)
            success_rate = successful_ops / total_ops if total_ops > 0 else 0.0
            error_rate = 1.0 - success_rate

            # Calculate throughput (operations per minute)
            time_span_minutes = hours * 60
            throughput_ops_per_minute = total_ops / time_span_minutes if time_span_minutes > 0 else 0.0

            metrics = PerformanceMetrics(
                provider=prov,
                operation_type=op_type,
                avg_latency_ms=avg_latency,
                p95_latency_ms=p95_latency,
                p99_latency_ms=p99_latency,
                success_rate=success_rate,
                throughput_ops_per_minute=throughput_ops_per_minute,
                error_rate=error_rate,
                sample_count=total_ops,
                time_period_hours=hours
            )

            # Add to cache
            metrics.cached_at = datetime.now()
            self._performance_cache[f"{prov}_{op_type}_{hours}h"] = metrics

            performance_metrics.append(metrics)

            # Check for performance alerts
            await self._check_performance_alerts(metrics)

        return performance_metrics

    async def get_tenant_usage_stats(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get storage usage statistics for a specific tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dictionary with usage statistics
        """
        try:
            usage_metrics = await self.get_storage_usage_metrics(tenant_id=tenant_id)

            # Aggregate statistics
            total_files = 0
            total_size_bytes = 0
            by_provider = {}
            by_type = {}

            for metrics in usage_metrics:
                total_files += metrics.file_count
                total_size_bytes += metrics.total_size_bytes

                # Group by provider (if available in metrics)
                provider = getattr(metrics, 'provider', 'unknown')
                if provider not in by_provider:
                    by_provider[provider] = {'files': 0, 'size_bytes': 0}
                by_provider[provider]['files'] += metrics.file_count
                by_provider[provider]['size_bytes'] += metrics.total_size_bytes

                # Group by attachment type (if available in metrics)
                attachment_type = getattr(metrics, 'attachment_type', 'unknown')
                if attachment_type not in by_type:
                    by_type[attachment_type] = {'files': 0, 'size_bytes': 0}
                by_type[attachment_type]['files'] += metrics.file_count
                by_type[attachment_type]['size_bytes'] += metrics.total_size_bytes

            return {
                'total_files': total_files,
                'total_size_bytes': total_size_bytes,
                'by_provider': by_provider,
                'by_type': by_type
            }

        except Exception as e:
            logger.error(f"Failed to get tenant usage stats for {tenant_id}: {e}")
            return {
                'total_files': 0,
                'total_size_bytes': 0,
                'by_provider': {},
                'by_type': {}
            }

    async def get_operation_logs(
        self,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
        operation_type: Optional[str] = None,
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get storage operation logs for a tenant.

        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of logs to return
            offset: Number of logs to skip
            operation_type: Filter by operation type
            provider: Filter by provider

        Returns:
            List of operation log entries
        """
        try:
            from core.models.models import StorageOperationLog
            from sqlalchemy import desc

            # Build query
            query = self.db.query(StorageOperationLog).filter(
                StorageOperationLog.tenant_id == tenant_id
            )

            if operation_type:
                query = query.filter(StorageOperationLog.operation_type == operation_type)

            if provider:
                query = query.filter(StorageOperationLog.provider == provider)

            # Execute query with pagination
            logs = query.order_by(desc(StorageOperationLog.created_at)).offset(offset).limit(limit).all()

            # Convert to dictionaries
            log_entries = []
            for log in logs:
                log_entries.append({
                    'id': log.id,
                    'operation_type': log.operation_type,
                    'file_key': log.file_key,
                    'provider': log.provider,
                    'success': log.success,
                    'file_size': log.file_size,
                    'duration_ms': log.duration_ms,
                    'error_message': log.error_message,
                    'user_id': log.user_id,
                    'ip_address': log.ip_address,
                    'created_at': log.created_at.isoformat() if log.created_at else None
                })

            return log_entries

        except Exception as e:
            logger.error(f"Failed to get operation logs for tenant {tenant_id}: {e}")
            return []
