"""
Anti-spam protection for /api/leads/create:
1. Honeypot field — invisible input that bots fill but humans don't see.
2. Rate-limiting — N requests per IP per minute, in-memory sliding window.

Both are non-blocking: legitimate traffic passes silently.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Deque

logger = logging.getLogger(__name__)


# Honeypot — name of the invisible field. If it has any value → bot.
HONEYPOT_FIELD = "company_website"


def is_honeypot_triggered(payload: dict) -> bool:
    """True if honeypot field is set (which means a bot filled it)."""
    value = payload.get(HONEYPOT_FIELD)
    return bool(value)


class RateLimiter:
    """In-memory sliding-window rate limiter, per IP."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, Deque[float]] = {}

    def allow(self, ip: str) -> bool:
        now = time.monotonic()
        bucket = self._buckets.setdefault(ip, deque())
        cutoff = now - self.window_seconds
        # Prune old timestamps
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            return False
        bucket.append(now)
        return True

    def cleanup(self) -> None:
        """Optional periodic cleanup of empty buckets (call from a background task)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        empty_keys = []
        for ip, bucket in self._buckets.items():
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if not bucket:
                empty_keys.append(ip)
        for ip in empty_keys:
            del self._buckets[ip]


# Global limiter for the lead form — 5 leads per minute per IP is more than enough for humans.
lead_limiter = RateLimiter(max_requests=5, window_seconds=60)


def get_client_ip(request) -> str:
    """Best-effort IP extraction respecting Cloudflare / Render proxies."""
    # Cloudflare sets cf-connecting-ip; Render's proxy uses x-forwarded-for
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
