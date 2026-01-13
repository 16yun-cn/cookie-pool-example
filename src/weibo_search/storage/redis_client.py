"""Redis client and cookie storage."""

import json
from datetime import datetime
from functools import lru_cache
from typing import Optional

import redis

from weibo_search.config import get_logger, get_settings
from weibo_search.models import CookieBundle

logger = get_logger("storage")


@lru_cache
def get_redis() -> redis.Redis:
    """Get Redis connection."""
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


class CookieStore:
    """Cookie storage and management using Redis."""

    COOKIE_PREFIX = "weibo:cookie:"
    COOKIE_POOL_KEY = "weibo:cookie:pool"

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or get_redis()

    def save(self, bundle: CookieBundle) -> str:
        """Save cookie bundle to Redis."""
        key = f"{self.COOKIE_PREFIX}{bundle.id}"
        data = bundle.model_dump(mode="json")
        # Convert datetime to ISO string
        if isinstance(data.get("created_at"), datetime):
            data["created_at"] = data["created_at"].isoformat()
        
        self.redis.set(key, json.dumps(data, ensure_ascii=False))
        
        # Add to pool with score = created_at timestamp
        score = bundle.created_at.timestamp()
        self.redis.zadd(self.COOKIE_POOL_KEY, {bundle.id: score})
        
        logger.debug(f"Saved cookie bundle: {bundle.id}")
        return key

    def get(self, cookie_id: str) -> Optional[CookieBundle]:
        """Get cookie bundle by ID."""
        key = f"{self.COOKIE_PREFIX}{cookie_id}"
        data = self.redis.get(key)
        if not data:
            return None
        
        try:
            parsed = json.loads(data)
            return CookieBundle(**parsed)
        except Exception as e:
            logger.error(f"Failed to parse cookie {cookie_id}: {e}")
            return None

    def get_valid(self) -> Optional[CookieBundle]:
        """Get a valid (non-expired) cookie from the pool."""
        settings = get_settings()
        now = datetime.now().timestamp()
        min_score = now - settings.cookie_ttl
        
        # Get cookies created after min_score (not expired)
        cookie_ids = self.redis.zrangebyscore(
            self.COOKIE_POOL_KEY, min_score, now, start=0, num=1
        )
        
        if not cookie_ids:
            logger.debug("No valid cookies in pool")
            return None
        
        cookie_id = cookie_ids[0]
        bundle = self.get(cookie_id)
        
        if bundle and not bundle.is_expired:
            logger.debug(f"Got valid cookie: {cookie_id}")
            return bundle
        
        # Cookie expired, remove from pool
        self.remove(cookie_id)
        return self.get_valid()  # Recurse to find another

    def remove(self, cookie_id: str) -> None:
        """Remove cookie from pool and storage."""
        key = f"{self.COOKIE_PREFIX}{cookie_id}"
        self.redis.delete(key)
        self.redis.zrem(self.COOKIE_POOL_KEY, cookie_id)
        logger.debug(f"Removed cookie: {cookie_id}")

    def mark_invalid(self, cookie_id: str) -> None:
        """Mark cookie as invalid (e.g., got ok:-100)."""
        # For now, just remove it
        self.remove(cookie_id)
        logger.info(f"Marked cookie as invalid: {cookie_id}")

    def pool_size(self) -> int:
        """Get current pool size."""
        return self.redis.zcard(self.COOKIE_POOL_KEY)

    def clear_expired(self) -> int:
        """Clear expired cookies from pool."""
        settings = get_settings()
        now = datetime.now().timestamp()
        min_score = now - settings.cookie_ttl
        
        # Remove cookies older than TTL
        removed = self.redis.zremrangebyscore(self.COOKIE_POOL_KEY, 0, min_score)
        if removed:
            logger.info(f"Cleared {removed} expired cookies")
        return removed


class SearchResultStore:
    """Search result storage using Redis."""

    RESULT_PREFIX = "weibo:search:"

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or get_redis()

    def save(self, keyword: str, page: int, data: dict) -> str:
        """Save search result."""
        key = f"{self.RESULT_PREFIX}{keyword}:{page}"
        self.redis.set(key, json.dumps(data, ensure_ascii=False))
        # Set expiry of 24 hours
        self.redis.expire(key, 86400)
        logger.debug(f"Saved search result: {key}")
        return key

    def get(self, keyword: str, page: int) -> Optional[dict]:
        """Get search result."""
        key = f"{self.RESULT_PREFIX}{keyword}:{page}"
        data = self.redis.get(key)
        if data:
            return json.loads(data)
        return None
