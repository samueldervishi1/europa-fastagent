#!/usr/bin/env python3
"""
Request Caching Utility for MCP Servers
Provides simple in-memory caching with TTL support for API calls
"""

import hashlib
import time
from typing import Any, Dict, Optional, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class RequestCache:
    """Simple in-memory cache with TTL for HTTP requests"""

    def __init__(self, default_ttl: int = 300):  # 5 minutes default
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = default_ttl

    def _generate_key(
        self, method: str, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None, data: Optional[Union[str, bytes]] = None
    ) -> str:
        """Generate cache key from request parameters"""
        key_data = f"{method.upper()}:{url}"

        if params:
            sorted_params = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            key_data += f"?{sorted_params}"

        if headers:
            # Only include relevant headers for caching
            cache_headers = {k: v for k, v in headers.items() if k.lower() not in ["authorization", "user-agent", "accept-encoding"]}
            if cache_headers:
                sorted_headers = "&".join(f"{k}={v}" for k, v in sorted(cache_headers.items()))
                key_data += f"#{sorted_headers}"

        if data:
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="ignore")
            key_data += f":{data}"

        return hashlib.md5(key_data.encode()).hexdigest()

    def _is_expired(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry has expired"""
        return time.time() > cache_entry["expires_at"]

    def get(
        self, method: str, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None, data: Optional[Union[str, bytes]] = None
    ) -> Optional[requests.Response]:
        """Get cached response if available and not expired"""
        cache_key = self._generate_key(method, url, params, headers, data)

        if cache_key in self._cache:
            entry = self._cache[cache_key]
            if not self._is_expired(entry):
                # Return cached response
                return entry["response"]
            else:
                # Remove expired entry
                del self._cache[cache_key]

        return None

    def set(
        self,
        method: str,
        url: str,
        response: requests.Response,
        ttl: Optional[int] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        data: Optional[Union[str, bytes]] = None,
    ):
        """Cache response with TTL"""
        if ttl is None:
            ttl = self._default_ttl

        cache_key = self._generate_key(method, url, params, headers, data)

        # Only cache successful responses
        if 200 <= response.status_code < 400:
            self._cache[cache_key] = {"response": response, "expires_at": time.time() + ttl, "cached_at": time.time()}

    def clear_expired(self):
        """Remove all expired entries"""
        current_time = time.time()
        expired_keys = [key for key, entry in self._cache.items() if current_time > entry["expires_at"]]

        for key in expired_keys:
            del self._cache[key]

    def clear_all(self):
        """Clear entire cache"""
        self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        current_time = time.time()
        expired_count = sum(1 for entry in self._cache.values() if current_time > entry["expires_at"])

        return {"total_entries": len(self._cache), "active_entries": len(self._cache) - expired_count, "expired_entries": expired_count}


# Connection pooling setup
def create_session_with_pooling() -> requests.Session:
    """Create requests session with connection pooling and retry strategy"""
    session = requests.Session()

    # Connection pool configuration
    adapter = HTTPAdapter(
        pool_connections=10,  # Number of connection pools
        pool_maxsize=20,  # Max connections per pool
        max_retries=Retry(
            total=3, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"]
        ),
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Set reasonable timeouts
    session.timeout = (5, 30)  # (connect, read) timeout

    return session


# Global instances
_request_cache = RequestCache()
_http_session = create_session_with_pooling()


def cached_request(method: str, url: str, ttl: Optional[int] = None, **kwargs) -> requests.Response:
    """
    Make HTTP request with caching support

    Args:
        method: HTTP method
        url: Request URL
        ttl: Cache TTL in seconds (optional)
        **kwargs: Additional arguments for requests

    Returns:
        Response object
    """
    # Extract cacheable parameters
    params = kwargs.get("params")
    headers = kwargs.get("headers")
    data = kwargs.get("data")

    # Check cache first
    cached_response = _request_cache.get(method, url, params, headers, data)
    if cached_response is not None:
        return cached_response

    # Make request using session with connection pooling
    response = _http_session.request(method, url, **kwargs)

    # Cache response
    _request_cache.set(method, url, response, ttl, params, headers, data)

    return response


def clear_request_cache():
    """Clear all cached requests"""
    _request_cache.clear_all()


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics"""
    return _request_cache.get_stats()


def cleanup_expired_cache():
    """Remove expired cache entries"""
    _request_cache.clear_expired()


def get_pooled_session() -> requests.Session:
    """Get the global HTTP session with connection pooling"""
    return _http_session
