"""
Cloud Storage Logging Service

Comprehensive logging and monitoring service for cloud storage operations
with performance metrics, audit trails, and analytics capabilities.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.models_per_tenant import StorageOperationLog

logger = logging.getLogger(__name__)


class StorageLoggingService:
    """
    Service for logging and analyzing cloud storage operations.
    
    Provides comprehensive logging, performance metrics collection,
    and audit trail capabilities for storage operations.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the storage logging service.
        
        Args:
            db: Database session for logging operations
        """
        self.db = db
    
    async def log_operation(
        self,
        operation_type: str,
        file_key: str,
        provider: str,
        success: bool,
        tenant_id: str,
        user_id: int,
        file_size: Optional[int] = None,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log a storage operation with comprehensive details.
        
        Args:
            operation_type: Type of operation (upload, download, delete)
            file_key: File key
            provider: Storage provider name
            success: Whether operation was successful
            tenant_id: Tenant identifier
            user_id: User identifier
            file_size: File size in bytes
            duration_ms: Operation duration in milliseconds
            error_message: Error message if operation failed
            ip_address: Client IP address
            additional_metadata: Additional metadata
            
        Returns:
            True if logging was successful
        """
        try:
            log_entry = StorageOperationLog(
                operation_type=operation_type,
                file_key=file_key,
                provider=provider,
                success=success,
                file_size=file_size,
                duration_ms=duration_ms,
                error_message=error_message,
                user_id=user_id,
                ip_address=ip_address,
                operation_metadata=additional_metadata
            )
            
            self.db.add(log_entry)
            self.db.commit()
            
            logger.debug(f"Logged {operation_type} operation for file {file_key} "
                        f"(provider: {provider}, success: {success})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to log storage operation: {e}")
            try:
                self.db.rollback()
            except Exception:
                pass
            return False
    
    def get_operation_metrics(
        self,
        provider: Optional[str] = None,
        operation_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """
        Get comprehensive operation metrics.

        Args:
            provider: Filter by provider
            operation_type: Filter by operation type
            start_date: Start date for filtering
            end_date: End date for filtering
            limit: Maximum number of records to analyze

        Returns:
            Dictionary with operation metrics and statistics
        """
        try:
            # Build query with filters
            query = self.db.query(StorageOperationLog)

            if provider:
                query = query.filter(StorageOperationLog.provider == provider)
            if operation_type:
                query = query.filter(StorageOperationLog.operation_type == operation_type)
            if start_date:
                query = query.filter(StorageOperationLog.created_at >= start_date)
            if end_date:
                query = query.filter(StorageOperationLog.created_at <= end_date)
            
            # Get recent operations
            operations = query.order_by(desc(StorageOperationLog.created_at)).limit(limit).all()
            
            if not operations:
                return {
                    'total_operations': 0,
                    'success_rate': 0.0,
                    'average_duration_ms': 0.0,
                    'total_data_transferred': 0,
                    'operations_by_provider': {},
                    'operations_by_type': {},
                    'error_summary': {},
                    'performance_metrics': {}
                }
            
            # Calculate basic metrics
            total_operations = len(operations)
            successful_operations = sum(1 for op in operations if op.success)
            success_rate = (successful_operations / total_operations) * 100
            
            # Calculate duration metrics (excluding None values)
            durations = [op.duration_ms for op in operations if op.duration_ms is not None]
            avg_duration = sum(durations) / len(durations) if durations else 0.0
            
            # Calculate data transfer metrics
            file_sizes = [op.file_size for op in operations if op.file_size is not None]
            total_data = sum(file_sizes) if file_sizes else 0
            
            # Group by provider
            operations_by_provider = {}
            for op in operations:
                provider_name = op.provider
                if provider_name not in operations_by_provider:
                    operations_by_provider[provider_name] = {
                        'total': 0,
                        'successful': 0,
                        'failed': 0,
                        'success_rate': 0.0,
                        'avg_duration_ms': 0.0,
                        'total_data': 0
                    }
                
                stats = operations_by_provider[provider_name]
                stats['total'] += 1
                if op.success:
                    stats['successful'] += 1
                else:
                    stats['failed'] += 1
                
                if op.duration_ms:
                    # Update running average
                    current_avg = stats['avg_duration_ms']
                    stats['avg_duration_ms'] = (current_avg * (stats['total'] - 1) + op.duration_ms) / stats['total']
                
                if op.file_size:
                    stats['total_data'] += op.file_size
                
                stats['success_rate'] = (stats['successful'] / stats['total']) * 100
            
            # Group by operation type
            operations_by_type = {}
            for op in operations:
                op_type = op.operation_type
                if op_type not in operations_by_type:
                    operations_by_type[op_type] = {
                        'total': 0,
                        'successful': 0,
                        'failed': 0,
                        'success_rate': 0.0
                    }
                
                stats = operations_by_type[op_type]
                stats['total'] += 1
                if op.success:
                    stats['successful'] += 1
                else:
                    stats['failed'] += 1
                
                stats['success_rate'] = (stats['successful'] / stats['total']) * 100
            
            # Error summary
            error_summary = {}
            failed_operations = [op for op in operations if not op.success and op.error_message]
            for op in failed_operations:
                error_msg = op.error_message[:100]  # Truncate long error messages
                if error_msg not in error_summary:
                    error_summary[error_msg] = 0
                error_summary[error_msg] += 1
            
            # Performance metrics
            performance_metrics = {
                'fastest_operation_ms': min(durations) if durations else 0,
                'slowest_operation_ms': max(durations) if durations else 0,
                'median_duration_ms': sorted(durations)[len(durations) // 2] if durations else 0,
                'operations_per_hour': self._calculate_operations_per_hour(operations),
                'data_transfer_rate_mb_per_second': self._calculate_transfer_rate(operations)
            }
            
            return {
                'total_operations': total_operations,
                'successful_operations': successful_operations,
                'failed_operations': total_operations - successful_operations,
                'success_rate': round(success_rate, 2),
                'average_duration_ms': round(avg_duration, 2),
                'total_data_transferred': total_data,
                'operations_by_provider': operations_by_provider,
                'operations_by_type': operations_by_type,
                'error_summary': dict(sorted(error_summary.items(), key=lambda x: x[1], reverse=True)[:10]),
                'performance_metrics': performance_metrics,
                'analysis_period': {
                    'start': operations[-1].created_at.isoformat() if operations else None,
                    'end': operations[0].created_at.isoformat() if operations else None,
                    'records_analyzed': total_operations
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get operation metrics: {e}")
            return {'error': str(e)}
    
    def _calculate_operations_per_hour(self, operations: List[StorageOperationLog]) -> float:
        """Calculate operations per hour based on the time span of operations."""
        if len(operations) < 2:
            return 0.0
        
        start_time = operations[-1].created_at
        end_time = operations[0].created_at
        time_diff = end_time - start_time
        
        if time_diff.total_seconds() == 0:
            return 0.0
        
        hours = time_diff.total_seconds() / 3600
        return len(operations) / hours
    
    def _calculate_transfer_rate(self, operations: List[StorageOperationLog]) -> float:
        """Calculate average data transfer rate in MB/s."""
        transfer_operations = [
            op for op in operations 
            if op.file_size and op.duration_ms and op.duration_ms > 0
        ]
        
        if not transfer_operations:
            return 0.0
        
        total_mb = sum(op.file_size / (1024 * 1024) for op in transfer_operations)
        total_seconds = sum(op.duration_ms / 1000 for op in transfer_operations)
        
        return total_mb / total_seconds if total_seconds > 0 else 0.0
    
    def get_provider_performance_comparison(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Compare performance across different storage providers.

        Args:
            days: Number of days to analyze

        Returns:
            Dictionary with provider performance comparison
        """
        try:
            start_date = datetime.now() - timedelta(days=days)

            query = self.db.query(StorageOperationLog).filter(
                StorageOperationLog.created_at >= start_date
            )
            
            operations = query.all()
            
            if not operations:
                return {'error': 'No operations found for the specified period'}
            
            # Group operations by provider
            provider_stats = {}
            
            for op in operations:
                provider = op.provider
                if provider not in provider_stats:
                    provider_stats[provider] = {
                        'operations': [],
                        'total_operations': 0,
                        'successful_operations': 0,
                        'total_data': 0,
                        'total_duration': 0,
                        'upload_count': 0,
                        'download_count': 0,
                        'delete_count': 0
                    }
                
                stats = provider_stats[provider]
                stats['operations'].append(op)
                stats['total_operations'] += 1
                
                if op.success:
                    stats['successful_operations'] += 1
                
                if op.file_size:
                    stats['total_data'] += op.file_size
                
                if op.duration_ms:
                    stats['total_duration'] += op.duration_ms
                
                # Count operation types
                if op.operation_type == 'upload':
                    stats['upload_count'] += 1
                elif op.operation_type == 'download':
                    stats['download_count'] += 1
                elif op.operation_type == 'delete':
                    stats['delete_count'] += 1
            
            # Calculate comparative metrics
            comparison = {}
            
            for provider, stats in provider_stats.items():
                total_ops = stats['total_operations']
                successful_ops = stats['successful_operations']
                
                comparison[provider] = {
                    'total_operations': total_ops,
                    'success_rate': (successful_ops / total_ops * 100) if total_ops > 0 else 0,
                    'average_duration_ms': (stats['total_duration'] / total_ops) if total_ops > 0 else 0,
                    'total_data_mb': stats['total_data'] / (1024 * 1024),
                    'operations_breakdown': {
                        'upload': stats['upload_count'],
                        'download': stats['download_count'],
                        'delete': stats['delete_count']
                    },
                    'reliability_score': self._calculate_reliability_score(stats['operations']),
                    'performance_score': self._calculate_performance_score(stats['operations'])
                }
            
            # Rank providers
            ranked_providers = sorted(
                comparison.items(),
                key=lambda x: (x[1]['reliability_score'] + x[1]['performance_score']) / 2,
                reverse=True
            )
            
            return {
                'analysis_period_days': days,
                'provider_comparison': comparison,
                'provider_ranking': [{'provider': p[0], 'combined_score': (p[1]['reliability_score'] + p[1]['performance_score']) / 2} for p in ranked_providers],
                'recommendations': self._generate_provider_recommendations(comparison)
            }
            
        except Exception as e:
            logger.error(f"Failed to get provider performance comparison: {e}")
            return {'error': str(e)}
    
    def _calculate_reliability_score(self, operations: List[StorageOperationLog]) -> float:
        """Calculate reliability score (0-100) based on success rate and consistency."""
        if not operations:
            return 0.0
        
        success_rate = sum(1 for op in operations if op.success) / len(operations)
        
        # Penalize for recent failures
        recent_operations = sorted(operations, key=lambda x: x.created_at, reverse=True)[:10]
        recent_success_rate = sum(1 for op in recent_operations if op.success) / len(recent_operations)
        
        # Weighted score (70% overall, 30% recent)
        reliability_score = (success_rate * 0.7 + recent_success_rate * 0.3) * 100
        
        return round(reliability_score, 2)
    
    def _calculate_performance_score(self, operations: List[StorageOperationLog]) -> float:
        """Calculate performance score (0-100) based on speed and consistency."""
        if not operations:
            return 0.0
        
        # Get operations with duration data
        timed_operations = [op for op in operations if op.duration_ms is not None]
        
        if not timed_operations:
            return 50.0  # Neutral score if no timing data
        
        durations = [op.duration_ms for op in timed_operations]
        avg_duration = sum(durations) / len(durations)
        
        # Score based on average duration (lower is better)
        # Assume 1000ms is baseline (score 50), scale from there
        baseline_duration = 1000
        if avg_duration <= baseline_duration:
            performance_score = 50 + (baseline_duration - avg_duration) / baseline_duration * 50
        else:
            performance_score = max(0, 50 - (avg_duration - baseline_duration) / baseline_duration * 50)
        
        return round(min(100, max(0, performance_score)), 2)
    
    def _generate_provider_recommendations(self, comparison: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on provider performance analysis."""
        recommendations = []
        
        if not comparison:
            return recommendations
        
        # Find best and worst performers
        providers_by_reliability = sorted(
            comparison.items(),
            key=lambda x: x[1]['reliability_score'],
            reverse=True
        )
        
        providers_by_performance = sorted(
            comparison.items(),
            key=lambda x: x[1]['performance_score'],
            reverse=True
        )
        
        if providers_by_reliability:
            best_reliability = providers_by_reliability[0]
            worst_reliability = providers_by_reliability[-1]
            
            if best_reliability[1]['reliability_score'] > 95:
                recommendations.append(f"{best_reliability[0]} shows excellent reliability ({best_reliability[1]['reliability_score']:.1f}%)")
            
            if worst_reliability[1]['reliability_score'] < 80:
                recommendations.append(f"{worst_reliability[0]} has reliability concerns ({worst_reliability[1]['reliability_score']:.1f}%)")
        
        if providers_by_performance:
            best_performance = providers_by_performance[0]
            worst_performance = providers_by_performance[-1]
            
            if best_performance[1]['performance_score'] > 80:
                recommendations.append(f"{best_performance[0]} offers the best performance")
            
            if worst_performance[1]['performance_score'] < 40:
                recommendations.append(f"Consider optimizing {worst_performance[0]} configuration for better performance")
        
        # Check for providers with low usage
        for provider, stats in comparison.items():
            if stats['total_operations'] < 10:
                recommendations.append(f"{provider} has low usage - consider reviewing configuration")
        
        return recommendations
    
    def get_audit_trail(
        self,
        file_key: Optional[str] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit trail for storage operations.

        Args:
            file_key: Filter by specific file key
            user_id: Filter by user ID
            start_date: Start date for filtering
            end_date: End date for filtering
            limit: Maximum number of records to return

        Returns:
            List of audit trail entries
        """
        try:
            query = self.db.query(StorageOperationLog)
            
            if file_key:
                query = query.filter(StorageOperationLog.file_key == file_key)
            if user_id:
                query = query.filter(StorageOperationLog.user_id == user_id)
            if start_date:
                query = query.filter(StorageOperationLog.created_at >= start_date)
            if end_date:
                query = query.filter(StorageOperationLog.created_at <= end_date)
            
            operations = query.order_by(desc(StorageOperationLog.created_at)).limit(limit).all()
            
            audit_entries = []
            for op in operations:
                audit_entries.append({
                    'id': op.id,
                    'timestamp': op.created_at.isoformat(),
                    'operation_type': op.operation_type,
                    'file_key': op.file_key,
                    'provider': op.provider,
                    'success': op.success,
                    'user_id': op.user_id,
                    'file_size': op.file_size,
                    'duration_ms': op.duration_ms,
                    'error_message': op.error_message,
                    'ip_address': op.ip_address
                })
            
            return audit_entries
            
        except Exception as e:
            logger.error(f"Failed to get audit trail: {e}")
            return []
    
    def cleanup_old_logs(self, days_to_keep: int = 90) -> int:
        """
        Clean up old log entries to manage database size.
        
        Args:
            days_to_keep: Number of days of logs to retain
            
        Returns:
            Number of log entries deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            deleted_count = self.db.query(StorageOperationLog).filter(
                StorageOperationLog.created_at < cutoff_date
            ).delete()
            
            self.db.commit()
            
            logger.info(f"Cleaned up {deleted_count} old storage operation logs")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")
            try:
                self.db.rollback()
            except Exception:
                pass
            return 0
