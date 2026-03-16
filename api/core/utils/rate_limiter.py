"""Rate limiter with Redis backend and in-memory fallback.

Uses Redis INCR + EXPIRE (fixed window) when REDIS_URL is configured.
Falls back to an in-memory sliding-window deque when Redis is unavailable.
The in-memory store is NOT shared across processes — use Redis for
multi-instance deployments.
"""
import time
import logging
from collections import defaultdict, deque
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_redis_client = None
_redis_checked = False  # avoid re-checking on every call after first failure

_in_memory_store: Dict[str, deque] = defaultdict(deque)


def _get_redis():
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    try:
        import redis as redis_lib
        from config import config
        if not config.REDIS_URL:
            logger.warning(
                "REDIS_URL is not set; rate limiter is using an in-memory store "
                "which is NOT shared across processes. This makes brute-force "
                "protection ineffective in multi-instance deployments."
            )
            return None
        client = redis_lib.from_url(
            config.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )
        client.ping()
        _redis_client = client
        logger.info("Rate limiter: Redis backend connected")
    except Exception as e:
        logger.warning(
            f"Rate limiter: Redis unavailable ({e}), falling back to in-memory store. "
            "Brute-force protection will not work across multiple instances."
        )
    return _redis_client


def record_and_check(key: str, max_attempts: int, window_seconds: int) -> bool:
    """Record one attempt for *key* and return True if the limit is exceeded.

    The caller should raise HTTP 429 when this returns True.
    The limit allows exactly *max_attempts* within *window_seconds*; the
    (max_attempts + 1)th call within the window will return True.
    """
    r = _get_redis()
    if r is not None:
        try:
            redis_key = f"rl:{key}"
            count = r.incr(redis_key)
            if count == 1:
                r.expire(redis_key, window_seconds)
            return count > max_attempts
        except Exception as e:
            logger.warning(f"Redis rate limit check failed, falling back to in-memory: {e}")

    # In-memory sliding-window fallback
    attempts = _in_memory_store[key]
    cutoff = time.time() - window_seconds
    while attempts and attempts[0] < cutoff:
        attempts.popleft()
    is_limited = len(attempts) >= max_attempts
    attempts.append(time.time())
    return is_limited
