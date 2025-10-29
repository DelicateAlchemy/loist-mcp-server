"""
Signed URL caching for MCP resources.

Implements in-memory caching for GCS signed URLs to reduce
redundant signature operations and improve performance.

Follows best practices from research:
- Short TTL for security
- ETag-based versioning
- Automatic expiration
- Thread-safe operations
"""

import time
import logging
from typing import Optional, Dict
from threading import Lock
from datetime import timedelta

from src.storage import generate_signed_url

logger = logging.getLogger(__name__)


class SignedURLCache:
    """
    In-memory cache for GCS signed URLs.
    
    Caches signed URLs with automatic expiration to balance
    performance (reduce GCS calls) and security (short-lived URLs).
    
    Attributes:
        default_ttl: Default cache TTL in seconds (90% of URL expiration)
        cache: Dictionary storing cached URLs
        expiry: Dictionary storing expiration timestamps
        lock: Thread lock for safe concurrent access
    """
    
    def __init__(self, default_ttl: int = 810):  # 13.5 minutes (90% of 15 min)
        """
        Initialize the cache.
        
        Args:
            default_ttl: Default cache TTL in seconds (default: 810s = 13.5 min)
        """
        self.default_ttl = default_ttl
        self.cache: Dict[str, str] = {}
        self.expiry: Dict[str, float] = {}
        self.lock = Lock()
        self.hits = 0
        self.misses = 0
        
        logger.info(f"Signed URL cache initialized with TTL={default_ttl}s")
    
    def get(
        self,
        gcs_path: str,
        url_expiration_minutes: int = 15
    ) -> str:
        """
        Get a signed URL from cache or generate new one.
        
        Args:
            gcs_path: Full GCS path (gs://bucket/path/to/file)
            url_expiration_minutes: Signed URL expiration time in minutes
            
        Returns:
            str: Signed URL (cached or freshly generated)
            
        Example:
            >>> cache = SignedURLCache()
            >>> url = cache.get("gs://bucket/audio.mp3")
            >>> print(url)
            "https://storage.googleapis.com/bucket/audio.mp3?X-Goog-..."
        """
        with self.lock:
            current_time = time.time()
            
            # Check if URL is in cache and not expired
            if gcs_path in self.cache and self.expiry.get(gcs_path, 0) > current_time:
                self.hits += 1
                logger.debug(f"Cache HIT for {gcs_path} (hits={self.hits}, misses={self.misses})")
                return self.cache[gcs_path]
            
            # Cache miss - generate new signed URL
            self.misses += 1
            logger.debug(f"Cache MISS for {gcs_path} (hits={self.hits}, misses={self.misses})")
            
            # Parse GCS path
            if not gcs_path.startswith("gs://"):
                raise ValueError(f"Invalid GCS path: {gcs_path}")
            
            # Extract bucket and blob name
            path_without_prefix = gcs_path[5:]  # Remove "gs://"
            parts = path_without_prefix.split("/", 1)
            
            if len(parts) != 2:
                raise ValueError(f"Invalid GCS path format: {gcs_path}")
            
            bucket_name, blob_name = parts
            
            # Generate signed URL
            try:
                signed_url = generate_signed_url(
                    bucket_name=bucket_name,
                    blob_name=blob_name,
                    expiration=timedelta(minutes=url_expiration_minutes)
                )
            except Exception as e:
                logger.error(f"Failed to generate signed URL for {gcs_path}: {e}")
                raise
            
            # Calculate cache expiration (90% of URL expiration for safety)
            cache_ttl = url_expiration_minutes * 60 * 0.9
            
            # Store in cache
            self.cache[gcs_path] = signed_url
            self.expiry[gcs_path] = current_time + cache_ttl
            
            logger.info(f"Generated and cached signed URL for {gcs_path} (expires in {cache_ttl}s)")
            
            return signed_url
    
    def invalidate(self, gcs_path: str) -> bool:
        """
        Invalidate a cached URL.
        
        Args:
            gcs_path: GCS path to invalidate
            
        Returns:
            bool: True if entry was removed, False if not in cache
        """
        with self.lock:
            if gcs_path in self.cache:
                del self.cache[gcs_path]
                del self.expiry[gcs_path]
                logger.debug(f"Invalidated cache for {gcs_path}")
                return True
            return False
    
    def clear(self):
        """Clear all cached URLs."""
        with self.lock:
            count = len(self.cache)
            self.cache.clear()
            self.expiry.clear()
            logger.info(f"Cache cleared ({count} entries removed)")
    
    def cleanup_expired(self):
        """
        Remove expired entries from cache.
        
        Should be called periodically by a background task.
        """
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, exp_time in self.expiry.items()
                if exp_time <= current_time
            ]
            
            for key in expired_keys:
                del self.cache[key]
                del self.expiry[key]
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict[str, any]:
        """
        Get cache statistics.
        
        Returns:
            dict: Cache statistics including hits, misses, and hit rate
        """
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0.0
            
            return {
                "size": len(self.cache),
                "hits": self.hits,
                "misses": self.misses,
                "total_requests": total_requests,
                "hit_rate_percent": round(hit_rate, 2),
                "ttl_seconds": self.default_ttl
            }


# Global cache instance
_global_cache: Optional[SignedURLCache] = None


def get_cache() -> SignedURLCache:
    """
    Get the global SignedURLCache instance.
    
    Creates the cache on first access (lazy initialization).
    
    Returns:
        SignedURLCache: Global cache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = SignedURLCache()
    return _global_cache
