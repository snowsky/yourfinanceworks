"""
Report Caching Service

This service provides comprehensive caching capabilities for report generation,
including result caching, query optimization, and cache invalidation strategies.
"""

import json
import hashlib
import pickle
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging
import threading
from collections import OrderedDict

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from schemas.report import ReportData, ReportType, ExportFormat


class CacheStrategy(Enum):
    """Cache strategy options"""
    MEMORY_ONLY = "memory_only"
    REDIS_ONLY = "redis_only"
    HYBRID = "hybrid"


@dataclass
class CacheConfig:
    """Configuration for caching behavior"""
    strategy: CacheStrategy = CacheStrategy.MEMORY_ONLY
    default_ttl: int = 3600  # 1 hour in seconds
    max_memory_size: int = 100  # Maximum number of items in memory cache
    max_result_size: int = 50 * 1024 * 1024  # 50MB max result size to cache
    enable_compression: bool = True
    cache_key_prefix: str = "report_cache"
    redis_url: Optional[str] = None
    redis_db: int = 0
    redis_max_connections: int = 10


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    data: Any
    created_at: datetime
    expires_at: datetime
    size_bytes: int
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    compressed: bool = False


class ReportCacheService:
    """
    Comprehensive caching service for report generation with multiple strategies
    and automatic cache management.
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.logger = logging.getLogger(__name__)
        
        # Memory cache using OrderedDict for LRU behavior
        self._memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._cache_lock = threading.RLock()
        
        # Redis connection
        self._redis_client: Optional[redis.Redis] = None
        if self.config.strategy in [CacheStrategy.REDIS_ONLY, CacheStrategy.HYBRID]:
            self._init_redis()
        
        # Cache statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'total_size_bytes': 0,
            'redis_hits': 0,
            'redis_misses': 0,
            'memory_hits': 0,
            'memory_misses': 0
        }
        
        self.logger.info(f"Initialized ReportCacheService with strategy: {self.config.strategy}")
    
    def _init_redis(self) -> None:
        """Initialize Redis connection"""
        if not REDIS_AVAILABLE:
            self.logger.warning("Redis not available, falling back to memory-only caching")
            self.config.strategy = CacheStrategy.MEMORY_ONLY
            return
        
        if not self.config.redis_url:
            self.logger.warning("Redis URL not configured, falling back to memory-only caching")
            self.config.strategy = CacheStrategy.MEMORY_ONLY
            return
        
        try:
            self._redis_client = redis.from_url(
                self.config.redis_url,
                db=self.config.redis_db,
                max_connections=self.config.redis_max_connections,
                decode_responses=False  # We handle binary data
            )
            
            # Test connection
            self._redis_client.ping()
            self.logger.info(f"Connected to Redis at {self.config.redis_url}")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {e}")
            self.logger.warning("Falling back to memory-only caching")
            self.config.strategy = CacheStrategy.MEMORY_ONLY
            self._redis_client = None
    
    def get_cache_key(
        self,
        report_type: ReportType,
        filters: Dict[str, Any],
        export_format: ExportFormat,
        user_id: Optional[int] = None,
        additional_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a unique cache key for the given parameters.
        
        Args:
            report_type: Type of report
            filters: Report filters
            export_format: Export format
            user_id: User ID (for user-specific caching)
            additional_params: Additional parameters to include in key
            
        Returns:
            Unique cache key string
        """
        # Create a deterministic representation of the parameters
        key_data = {
            'report_type': report_type.value if isinstance(report_type, ReportType) else str(report_type),
            'filters': self._normalize_filters(filters),
            'export_format': export_format.value if isinstance(export_format, ExportFormat) else str(export_format),
            'user_id': user_id
        }
        
        if additional_params:
            key_data['additional'] = additional_params
        
        # Create JSON string and hash it
        key_json = json.dumps(key_data, sort_keys=True, default=str)
        key_hash = hashlib.sha256(key_json.encode()).hexdigest()
        
        return f"{self.config.cache_key_prefix}:{key_hash}"
    
    def _normalize_filters(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize filters for consistent cache key generation.
        
        Args:
            filters: Raw filters dictionary
            
        Returns:
            Normalized filters dictionary
        """
        normalized = {}
        
        for key, value in filters.items():
            if value is None:
                continue
                
            if isinstance(value, datetime):
                normalized[key] = value.isoformat()
            elif isinstance(value, list):
                # Sort lists for consistent ordering
                normalized[key] = sorted([str(v) for v in value])
            else:
                normalized[key] = str(value)
        
        return normalized
    
    def get(self, cache_key: str) -> Optional[Any]:
        """
        Retrieve data from cache.
        
        Args:
            cache_key: Cache key to retrieve
            
        Returns:
            Cached data if found and not expired, None otherwise
        """
        # Try memory cache first for hybrid strategy
        if self.config.strategy in [CacheStrategy.MEMORY_ONLY, CacheStrategy.HYBRID]:
            result = self._get_from_memory(cache_key)
            if result is not None:
                self._stats['memory_hits'] += 1
                self._stats['hits'] += 1
                return result
            else:
                self._stats['memory_misses'] += 1
        
        # Try Redis cache
        if self.config.strategy in [CacheStrategy.REDIS_ONLY, CacheStrategy.HYBRID] and self._redis_client:
            result = self._get_from_redis(cache_key)
            if result is not None:
                self._stats['redis_hits'] += 1
                self._stats['hits'] += 1
                
                # Store in memory cache for hybrid strategy
                if self.config.strategy == CacheStrategy.HYBRID:
                    self._set_in_memory(cache_key, result)
                
                return result
            else:
                self._stats['redis_misses'] += 1
        
        self._stats['misses'] += 1
        return None
    
    def _get_from_memory(self, cache_key: str) -> Optional[Any]:
        """Get data from memory cache"""
        with self._cache_lock:
            entry = self._memory_cache.get(cache_key)
            
            if entry is None:
                return None
            
            # Check if entry has expired
            if datetime.now() > entry.expires_at:
                self._remove_entry(cache_key)
                return None
            
            # Update access statistics
            entry.access_count += 1
            entry.last_accessed = datetime.now()
            
            # Move to end for LRU behavior
            self._memory_cache.move_to_end(cache_key)
            
            # Decompress if needed
            if entry.compressed:
                try:
                    return pickle.loads(entry.data)
                except Exception as e:
                    self.logger.error(f"Failed to decompress cache entry {cache_key}: {e}")
                    self._remove_entry(cache_key)
                    return None
            
            return entry.data
    
    def _get_from_redis(self, cache_key: str) -> Optional[Any]:
        """Get data from Redis cache"""
        if not self._redis_client:
            return None
        
        try:
            # Get data from Redis
            data = self._redis_client.get(cache_key)
            if data is None:
                return None
            
            # Deserialize data
            return pickle.loads(data)
            
        except Exception as e:
            self.logger.error(f"Error retrieving from Redis cache {cache_key}: {e}")
            return None
    
    def set(
        self,
        cache_key: str,
        data: Any,
        ttl: Optional[int] = None,
        force: bool = False
    ) -> bool:
        """
        Store data in cache.
        
        Args:
            cache_key: Cache key
            data: Data to cache
            ttl: Time to live in seconds (uses default if None)
            force: Force caching even if data is large
            
        Returns:
            True if data was cached, False otherwise
        """
        if data is None:
            return False
        
        ttl = ttl or self.config.default_ttl
        
        # Serialize data
        try:
            serialized_data = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
            data_size = len(serialized_data)
        except Exception as e:
            self.logger.warning(f"Failed to serialize data for caching: {e}")
            return False
        
        # Check size limits
        if not force and data_size > self.config.max_result_size:
            self.logger.warning(f"Data too large to cache: {data_size} bytes > {self.config.max_result_size}")
            return False
        
        success = False
        
        # Store in Redis
        if self.config.strategy in [CacheStrategy.REDIS_ONLY, CacheStrategy.HYBRID] and self._redis_client:
            success = self._set_in_redis(cache_key, serialized_data, ttl) or success
        
        # Store in memory
        if self.config.strategy in [CacheStrategy.MEMORY_ONLY, CacheStrategy.HYBRID]:
            success = self._set_in_memory(cache_key, data, ttl, data_size) or success
        
        if success:
            self.logger.debug(f"Cached data with key {cache_key}, size: {data_size} bytes, TTL: {ttl}s")
        
        return success
    
    def _set_in_memory(
        self, 
        cache_key: str, 
        data: Any, 
        ttl: Optional[int] = None, 
        data_size: Optional[int] = None
    ) -> bool:
        """Set data in memory cache"""
        ttl = ttl or self.config.default_ttl
        expires_at = datetime.now() + timedelta(seconds=ttl)
        
        if data_size is None:
            try:
                data_size = len(pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL))
            except Exception:
                data_size = len(str(data).encode('utf-8'))
        
        with self._cache_lock:
            # Create cache entry
            entry = CacheEntry(
                key=cache_key,
                data=data,
                created_at=datetime.now(),
                expires_at=expires_at,
                size_bytes=data_size,
                compressed=False
            )
            
            # Remove existing entry if present
            if cache_key in self._memory_cache:
                self._remove_entry(cache_key)
            
            # Ensure we have space
            self._ensure_cache_space(data_size)
            
            # Add new entry
            self._memory_cache[cache_key] = entry
            self._stats['total_size_bytes'] += data_size
            
            return True
    
    def _set_in_redis(self, cache_key: str, serialized_data: bytes, ttl: int) -> bool:
        """Set data in Redis cache"""
        if not self._redis_client:
            return False
        
        try:
            # Store in Redis with TTL
            self._redis_client.setex(cache_key, ttl, serialized_data)
            return True
            
        except Exception as e:
            self.logger.error(f"Error storing in Redis cache {cache_key}: {e}")
            return False
    
    def _ensure_cache_space(self, required_size: int) -> None:
        """
        Ensure there's enough space in cache by evicting old entries if needed.
        
        Args:
            required_size: Size in bytes that needs to be available
        """
        # Check if we need to evict based on count
        while len(self._memory_cache) >= self.config.max_memory_size:
            self._evict_lru_entry()
        
        # For now, we don't implement size-based eviction beyond the max_result_size check
        # This could be enhanced to have a total cache size limit
    
    def _evict_lru_entry(self) -> None:
        """Evict the least recently used entry"""
        if not self._memory_cache:
            return
        
        # OrderedDict maintains insertion order, and we move accessed items to end
        # So the first item is the least recently used
        lru_key = next(iter(self._memory_cache))
        self._remove_entry(lru_key)
        self._stats['evictions'] += 1
        
        self.logger.debug(f"Evicted LRU cache entry: {lru_key}")
    
    def _remove_entry(self, cache_key: str) -> None:
        """Remove an entry from cache and update statistics"""
        entry = self._memory_cache.pop(cache_key, None)
        if entry:
            self._stats['total_size_bytes'] -= entry.size_bytes
    
    def invalidate(self, cache_key: str) -> bool:
        """
        Invalidate a specific cache entry.
        
        Args:
            cache_key: Cache key to invalidate
            
        Returns:
            True if entry was found and removed, False otherwise
        """
        found = False
        
        # Remove from memory cache
        if self.config.strategy in [CacheStrategy.MEMORY_ONLY, CacheStrategy.HYBRID]:
            with self._cache_lock:
                if cache_key in self._memory_cache:
                    self._remove_entry(cache_key)
                    found = True
        
        # Remove from Redis cache
        if self.config.strategy in [CacheStrategy.REDIS_ONLY, CacheStrategy.HYBRID] and self._redis_client:
            try:
                result = self._redis_client.delete(cache_key)
                if result > 0:
                    found = True
            except Exception as e:
                self.logger.error(f"Error invalidating Redis cache entry {cache_key}: {e}")
        
        if found:
            self.logger.debug(f"Invalidated cache entry: {cache_key}")
        
        return found
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Pattern to match (simple string contains)
            
        Returns:
            Number of entries invalidated
        """
        total_invalidated = 0
        
        # Invalidate from memory cache
        if self.config.strategy in [CacheStrategy.MEMORY_ONLY, CacheStrategy.HYBRID]:
            with self._cache_lock:
                keys_to_remove = [
                    key for key in self._memory_cache.keys()
                    if pattern in key
                ]
                
                for key in keys_to_remove:
                    self._remove_entry(key)
                
                total_invalidated += len(keys_to_remove)
        
        # Invalidate from Redis cache
        if self.config.strategy in [CacheStrategy.REDIS_ONLY, CacheStrategy.HYBRID] and self._redis_client:
            try:
                # Use Redis SCAN to find matching keys
                cursor = 0
                redis_keys_removed = 0
                
                while True:
                    cursor, keys = self._redis_client.scan(
                        cursor=cursor,
                        match=f"*{pattern}*",
                        count=100
                    )
                    
                    if keys:
                        deleted = self._redis_client.delete(*keys)
                        redis_keys_removed += deleted
                    
                    if cursor == 0:
                        break
                
                total_invalidated += redis_keys_removed
                
            except Exception as e:
                self.logger.error(f"Error invalidating Redis cache pattern {pattern}: {e}")
        
        if total_invalidated > 0:
            self.logger.debug(f"Invalidated {total_invalidated} cache entries matching pattern: {pattern}")
        
        return total_invalidated
    
    def invalidate_user_cache(self, user_id: int) -> int:
        """
        Invalidate all cache entries for a specific user.
        
        Args:
            user_id: User ID to invalidate cache for
            
        Returns:
            Number of entries invalidated
        """
        return self.invalidate_pattern(f"user_id\":{user_id}")
    
    def invalidate_report_type(self, report_type: ReportType) -> int:
        """
        Invalidate all cache entries for a specific report type.
        
        Args:
            report_type: Report type to invalidate
            
        Returns:
            Number of entries invalidated
        """
        return self.invalidate_pattern(f"report_type\":\"{report_type.value}\"")
    
    def clear_all(self) -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of entries cleared
        """
        total_cleared = 0
        
        # Clear memory cache
        if self.config.strategy in [CacheStrategy.MEMORY_ONLY, CacheStrategy.HYBRID]:
            with self._cache_lock:
                count = len(self._memory_cache)
                self._memory_cache.clear()
                self._stats['total_size_bytes'] = 0
                total_cleared += count
        
        # Clear Redis cache (only keys with our prefix)
        if self.config.strategy in [CacheStrategy.REDIS_ONLY, CacheStrategy.HYBRID] and self._redis_client:
            try:
                cursor = 0
                redis_keys_removed = 0
                
                while True:
                    cursor, keys = self._redis_client.scan(
                        cursor=cursor,
                        match=f"{self.config.cache_key_prefix}:*",
                        count=100
                    )
                    
                    if keys:
                        deleted = self._redis_client.delete(*keys)
                        redis_keys_removed += deleted
                    
                    if cursor == 0:
                        break
                
                total_cleared += redis_keys_removed
                
            except Exception as e:
                self.logger.error(f"Error clearing Redis cache: {e}")
        
        self.logger.info(f"Cleared all cache entries: {total_cleared} entries")
        return total_cleared
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired cache entries.
        
        Returns:
            Number of entries removed
        """
        now = datetime.now()
        expired_keys = []
        
        with self._cache_lock:
            for key, entry in self._memory_cache.items():
                if now > entry.expires_at:
                    expired_keys.append(key)
            
            for key in expired_keys:
                self._remove_entry(key)
        
        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        with self._cache_lock:
            hit_rate = (
                self._stats['hits'] / (self._stats['hits'] + self._stats['misses'])
                if (self._stats['hits'] + self._stats['misses']) > 0
                else 0.0
            )
            
            memory_hit_rate = (
                self._stats['memory_hits'] / (self._stats['memory_hits'] + self._stats['memory_misses'])
                if (self._stats['memory_hits'] + self._stats['memory_misses']) > 0
                else 0.0
            )
            
            redis_hit_rate = (
                self._stats['redis_hits'] / (self._stats['redis_hits'] + self._stats['redis_misses'])
                if (self._stats['redis_hits'] + self._stats['redis_misses']) > 0
                else 0.0
            )
            
            stats = {
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate': hit_rate,
                'evictions': self._stats['evictions'],
                'memory_entries': len(self._memory_cache),
                'memory_size_bytes': self._stats['total_size_bytes'],
                'memory_size_mb': round(self._stats['total_size_bytes'] / (1024 * 1024), 2),
                'memory_hits': self._stats['memory_hits'],
                'memory_misses': self._stats['memory_misses'],
                'memory_hit_rate': memory_hit_rate,
                'redis_hits': self._stats['redis_hits'],
                'redis_misses': self._stats['redis_misses'],
                'redis_hit_rate': redis_hit_rate,
                'max_memory_entries': self.config.max_memory_size,
                'cache_strategy': self.config.strategy.value,
                'redis_connected': self._redis_client is not None
            }
            
            # Add Redis-specific stats if available
            if self._redis_client:
                try:
                    redis_info = self._redis_client.info('memory')
                    stats.update({
                        'redis_memory_used': redis_info.get('used_memory', 0),
                        'redis_memory_used_mb': round(redis_info.get('used_memory', 0) / (1024 * 1024), 2),
                        'redis_memory_peak': redis_info.get('used_memory_peak', 0)
                    })
                except Exception as e:
                    self.logger.debug(f"Could not get Redis memory stats: {e}")
            
            return stats
    
    def get_cache_info(self) -> List[Dict[str, Any]]:
        """
        Get detailed information about cached entries.
        
        Returns:
            List of cache entry information
        """
        with self._cache_lock:
            entries = []
            for key, entry in self._memory_cache.items():
                entries.append({
                    'key': key,
                    'created_at': entry.created_at.isoformat(),
                    'expires_at': entry.expires_at.isoformat(),
                    'size_bytes': entry.size_bytes,
                    'access_count': entry.access_count,
                    'last_accessed': entry.last_accessed.isoformat() if entry.last_accessed else None,
                    'compressed': entry.compressed,
                    'ttl_remaining': max(0, (entry.expires_at - datetime.now()).total_seconds())
                })
            
            return entries


# Global cache service instance
_cache_service: Optional[ReportCacheService] = None


def get_cache_service(config: Optional[CacheConfig] = None) -> ReportCacheService:
    """
    Get the global cache service instance.
    
    Args:
        config: Optional cache configuration (only used on first call)
        
    Returns:
        ReportCacheService instance
    """
    global _cache_service
    
    if _cache_service is None:
        _cache_service = ReportCacheService(config)
    
    return _cache_service


def invalidate_data_cache(entity_type: str, entity_id: Optional[int] = None) -> None:
    """
    Invalidate cache entries when data changes.
    
    Args:
        entity_type: Type of entity that changed (client, invoice, payment, etc.)
        entity_id: Optional specific entity ID
    """
    cache_service = get_cache_service()
    
    # Invalidate based on entity type
    patterns = []
    
    if entity_type == "client":
        patterns.append("CLIENT")
        if entity_id:
            patterns.append(f"client_ids\":[{entity_id}")
            patterns.append(f"client_ids\":[.*{entity_id}")
    elif entity_type == "invoice":
        patterns.extend(["INVOICE", "CLIENT", "PAYMENT"])  # Invoices affect multiple report types
    elif entity_type == "payment":
        patterns.extend(["PAYMENT", "INVOICE", "CLIENT"])
    elif entity_type == "expense":
        patterns.append("EXPENSE")
    elif entity_type == "statement":
        patterns.append("STATEMENT")
    
    total_invalidated = 0
    for pattern in patterns:
        total_invalidated += cache_service.invalidate_pattern(pattern)
    
    if total_invalidated > 0:
        logging.getLogger(__name__).debug(
            f"Invalidated {total_invalidated} cache entries for {entity_type} change"
        )