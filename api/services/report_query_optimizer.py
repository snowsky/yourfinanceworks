"""
Report Query Optimization Service

This service provides query optimization strategies for large datasets,
including pagination, indexing recommendations, and query performance monitoring.
"""

from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging
import time
from sqlalchemy.orm import Session, Query
from sqlalchemy import text, func, and_, or_
from sqlalchemy.sql import Select

from schemas.report import ReportFilters


class OptimizationStrategy(Enum):
    """Query optimization strategies"""
    PAGINATION = "pagination"
    INDEXING = "indexing"
    QUERY_REWRITE = "query_rewrite"
    RESULT_LIMITING = "result_limiting"
    EAGER_LOADING = "eager_loading"


@dataclass
class QueryPerformanceMetrics:
    """Performance metrics for query execution"""
    query_hash: str
    execution_time: float
    row_count: int
    memory_usage: Optional[int] = None
    cache_hit: bool = False
    optimization_applied: List[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.optimization_applied is None:
            self.optimization_applied = []


@dataclass
class PaginationConfig:
    """Configuration for query pagination"""
    page_size: int = 1000
    max_pages: int = 100
    enable_cursor_pagination: bool = True
    cursor_field: str = "id"


@dataclass
class OptimizationConfig:
    """Configuration for query optimization"""
    enable_pagination: bool = True
    enable_query_monitoring: bool = True
    slow_query_threshold: float = 5.0  # seconds
    max_result_size: int = 50000  # maximum rows without pagination
    pagination_config: PaginationConfig = None
    
    def __post_init__(self):
        if self.pagination_config is None:
            self.pagination_config = PaginationConfig()


class ReportQueryOptimizer:
    """
    Service for optimizing database queries used in report generation.
    Provides pagination, performance monitoring, and optimization strategies.
    """
    
    def __init__(self, db: Session, config: Optional[OptimizationConfig] = None):
        self.db = db
        self.config = config or OptimizationConfig()
        self.logger = logging.getLogger(__name__)
        
        # Performance tracking
        self._query_metrics: List[QueryPerformanceMetrics] = []
        self._max_metrics_history = 1000
        
        # Query optimization cache
        self._optimization_cache: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info("Initialized ReportQueryOptimizer")
    
    def optimize_query(
        self,
        query: Query,
        filters: Optional[ReportFilters] = None,
        expected_size: Optional[int] = None
    ) -> Tuple[Query, Dict[str, Any]]:
        """
        Optimize a query based on filters and expected result size.
        
        Args:
            query: SQLAlchemy query to optimize
            filters: Report filters that might affect optimization
            expected_size: Expected number of results
            
        Returns:
            Tuple of (optimized_query, optimization_info)
        """
        optimization_info = {
            'strategies_applied': [],
            'estimated_rows': expected_size,
            'pagination_applied': False,
            'eager_loading_applied': False
        }
        
        optimized_query = query
        
        # Apply eager loading optimization
        if self._should_apply_eager_loading(filters):
            optimized_query = self._apply_eager_loading(optimized_query, filters)
            optimization_info['strategies_applied'].append(OptimizationStrategy.EAGER_LOADING.value)
            optimization_info['eager_loading_applied'] = True
        
        # Apply result limiting if needed
        if expected_size and expected_size > self.config.max_result_size:
            optimized_query = self._apply_result_limiting(optimized_query, filters)
            optimization_info['strategies_applied'].append(OptimizationStrategy.RESULT_LIMITING.value)
        
        # Apply query rewriting optimizations
        optimized_query = self._apply_query_rewrite(optimized_query, filters)
        optimization_info['strategies_applied'].append(OptimizationStrategy.QUERY_REWRITE.value)
        
        return optimized_query, optimization_info
    
    def execute_with_pagination(
        self,
        query: Query,
        page_size: Optional[int] = None,
        max_pages: Optional[int] = None,
        progress_callback: Optional[callable] = None
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Execute a query with pagination to handle large result sets.
        
        Args:
            query: Query to execute
            page_size: Number of records per page
            max_pages: Maximum number of pages to fetch
            progress_callback: Optional callback for progress updates
            
        Returns:
            Tuple of (results, pagination_info)
        """
        page_size = page_size or self.config.pagination_config.page_size
        max_pages = max_pages or self.config.pagination_config.max_pages
        
        results = []
        pagination_info = {
            'total_pages': 0,
            'total_records': 0,
            'pages_fetched': 0,
            'execution_time': 0,
            'truncated': False
        }
        
        start_time = time.time()
        
        try:
            # Get total count first (with optimization)
            count_query = query.statement.with_only_columns(func.count()).order_by(None)
            total_count = self.db.execute(count_query).scalar()
            
            pagination_info['total_records'] = total_count
            pagination_info['total_pages'] = (total_count + page_size - 1) // page_size
            
            # Limit pages if necessary
            pages_to_fetch = min(pagination_info['total_pages'], max_pages)
            if pages_to_fetch < pagination_info['total_pages']:
                pagination_info['truncated'] = True
            
            # Fetch pages
            for page in range(pages_to_fetch):
                offset = page * page_size
                page_query = query.offset(offset).limit(page_size)
                
                page_results = page_query.all()
                results.extend(page_results)
                
                pagination_info['pages_fetched'] += 1
                
                # Call progress callback if provided
                if progress_callback:
                    progress = (page + 1) / pages_to_fetch
                    progress_callback(progress, len(results), total_count)
                
                # Break if we got fewer results than expected (end of data)
                if len(page_results) < page_size:
                    break
            
            pagination_info['execution_time'] = time.time() - start_time
            
            self.logger.debug(
                f"Paginated query executed: {pagination_info['pages_fetched']} pages, "
                f"{len(results)} records, {pagination_info['execution_time']:.2f}s"
            )
            
            return results, pagination_info
            
        except Exception as e:
            self.logger.error(f"Error in paginated query execution: {e}")
            raise
    
    def execute_with_monitoring(
        self,
        query: Query,
        query_name: str = "unnamed_query"
    ) -> Tuple[List[Any], QueryPerformanceMetrics]:
        """
        Execute a query with performance monitoring.
        
        Args:
            query: Query to execute
            query_name: Name for the query (for logging)
            
        Returns:
            Tuple of (results, performance_metrics)
        """
        query_hash = self._get_query_hash(query)
        start_time = time.time()
        
        try:
            results = query.all()
            execution_time = time.time() - start_time
            
            metrics = QueryPerformanceMetrics(
                query_hash=query_hash,
                execution_time=execution_time,
                row_count=len(results)
            )
            
            # Log slow queries
            if execution_time > self.config.slow_query_threshold:
                self.logger.warning(
                    f"Slow query detected: {query_name} took {execution_time:.2f}s "
                    f"and returned {len(results)} rows"
                )
            
            # Store metrics
            self._store_metrics(metrics)
            
            return results, metrics
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"Query execution failed after {execution_time:.2f}s: {e}")
            raise
    
    def get_optimization_recommendations(
        self,
        query: Query,
        filters: Optional[ReportFilters] = None
    ) -> List[Dict[str, Any]]:
        """
        Get optimization recommendations for a query.
        
        Args:
            query: Query to analyze
            filters: Report filters
            
        Returns:
            List of optimization recommendations
        """
        recommendations = []
        
        # Analyze query structure
        query_str = str(query.statement.compile(compile_kwargs={"literal_binds": True}))
        
        # Check for missing indexes
        index_recommendations = self._analyze_index_needs(query_str, filters)
        recommendations.extend(index_recommendations)
        
        # Check for inefficient joins
        join_recommendations = self._analyze_join_efficiency(query_str)
        recommendations.extend(join_recommendations)
        
        # Check for large result sets
        if filters:
            size_recommendations = self._analyze_result_size(filters)
            recommendations.extend(size_recommendations)
        
        return recommendations
    
    def _should_apply_eager_loading(self, filters: Optional[ReportFilters]) -> bool:
        """Determine if eager loading should be applied"""
        if not filters:
            return False
        
        # Apply eager loading for reports that typically need related data
        eager_loading_fields = ['include_items', 'include_attachments', 'include_reconciliation']
        return any(getattr(filters, field, False) for field in eager_loading_fields if hasattr(filters, field))
    
    def _apply_eager_loading(self, query: Query, filters: ReportFilters) -> Query:
        """Apply eager loading optimizations"""
        # This would be implemented based on the specific query and relationships
        # For now, return the query unchanged
        return query
    
    def _apply_result_limiting(self, query: Query, filters: Optional[ReportFilters]) -> Query:
        """Apply result limiting for large datasets"""
        # Add a reasonable limit to prevent memory issues
        return query.limit(self.config.max_result_size)
    
    def _apply_query_rewrite(self, query: Query, filters: Optional[ReportFilters]) -> Query:
        """Apply query rewriting optimizations"""
        # This could include:
        # - Converting subqueries to joins
        # - Optimizing WHERE clauses
        # - Adding query hints
        
        # For now, return the query unchanged
        return query
    
    def _get_query_hash(self, query: Query) -> str:
        """Generate a hash for the query for caching/tracking purposes"""
        query_str = str(query.statement.compile(compile_kwargs={"literal_binds": True}))
        import hashlib
        return hashlib.md5(query_str.encode()).hexdigest()
    
    def _store_metrics(self, metrics: QueryPerformanceMetrics) -> None:
        """Store query performance metrics"""
        self._query_metrics.append(metrics)
        
        # Keep only recent metrics
        if len(self._query_metrics) > self._max_metrics_history:
            self._query_metrics = self._query_metrics[-self._max_metrics_history:]
    
    def _analyze_index_needs(
        self,
        query_str: str,
        filters: Optional[ReportFilters]
    ) -> List[Dict[str, Any]]:
        """Analyze query for missing index recommendations"""
        recommendations = []
        
        # Common patterns that benefit from indexes
        index_patterns = {
            'date_filtering': ['created_at', 'updated_at', 'due_date', 'payment_date', 'expense_date'],
            'status_filtering': ['status', 'is_deleted'],
            'foreign_keys': ['client_id', 'invoice_id', 'user_id', 'tenant_id'],
            'amount_filtering': ['amount', 'balance', 'total_amount']
        }
        
        for pattern_name, fields in index_patterns.items():
            for field in fields:
                if field in query_str.lower():
                    recommendations.append({
                        'type': 'index',
                        'priority': 'medium',
                        'description': f"Consider adding index on {field} for {pattern_name}",
                        'field': field,
                        'pattern': pattern_name
                    })
        
        return recommendations
    
    def _analyze_join_efficiency(self, query_str: str) -> List[Dict[str, Any]]:
        """Analyze query for join efficiency"""
        recommendations = []
        
        # Count number of joins
        join_count = query_str.lower().count('join')
        
        if join_count > 3:
            recommendations.append({
                'type': 'join_optimization',
                'priority': 'high',
                'description': f"Query has {join_count} joins, consider denormalization or query splitting",
                'join_count': join_count
            })
        
        return recommendations
    
    def _analyze_result_size(self, filters: ReportFilters) -> List[Dict[str, Any]]:
        """Analyze expected result size and recommend optimizations"""
        recommendations = []
        
        # Check date range
        if hasattr(filters, 'date_from') and hasattr(filters, 'date_to'):
            if filters.date_from and filters.date_to:
                date_range = (filters.date_to - filters.date_from).days
                if date_range > 365:
                    recommendations.append({
                        'type': 'result_size',
                        'priority': 'medium',
                        'description': f"Large date range ({date_range} days) may return many results",
                        'suggestion': "Consider using pagination or smaller date ranges"
                    })
        
        return recommendations
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get query performance statistics"""
        if not self._query_metrics:
            return {
                'total_queries': 0,
                'average_execution_time': 0,
                'slow_queries': 0,
                'total_rows_processed': 0
            }
        
        execution_times = [m.execution_time for m in self._query_metrics]
        row_counts = [m.row_count for m in self._query_metrics]
        
        slow_queries = sum(1 for t in execution_times if t > self.config.slow_query_threshold)
        
        return {
            'total_queries': len(self._query_metrics),
            'average_execution_time': sum(execution_times) / len(execution_times),
            'max_execution_time': max(execution_times),
            'min_execution_time': min(execution_times),
            'slow_queries': slow_queries,
            'slow_query_percentage': (slow_queries / len(self._query_metrics)) * 100,
            'total_rows_processed': sum(row_counts),
            'average_rows_per_query': sum(row_counts) / len(row_counts)
        }
    
    def get_slow_queries(self, limit: int = 10) -> List[QueryPerformanceMetrics]:
        """Get the slowest queries"""
        sorted_metrics = sorted(
            self._query_metrics,
            key=lambda m: m.execution_time,
            reverse=True
        )
        return sorted_metrics[:limit]
    
    def clear_metrics(self) -> None:
        """Clear stored performance metrics"""
        self._query_metrics.clear()
        self.logger.info("Cleared query performance metrics")


# Global optimizer instance
_query_optimizer: Optional[ReportQueryOptimizer] = None


def get_query_optimizer(db: Session, config: Optional[OptimizationConfig] = None) -> ReportQueryOptimizer:
    """
    Get a query optimizer instance.
    
    Args:
        db: Database session
        config: Optional optimization configuration
        
    Returns:
        ReportQueryOptimizer instance
    """
    return ReportQueryOptimizer(db, config)