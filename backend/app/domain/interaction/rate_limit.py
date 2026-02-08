"""Rate limiting for interactions."""
from typing import Protocol
from datetime import datetime, timedelta


class RateLimiter(Protocol):
    """Rate limiter protocol."""

    async def check_rate_limit(
        self, key: str, max_requests: int, window_seconds: int
    ) -> bool:
        """
        Check if request is within rate limit.
        Returns True if allowed, False if rate limited.
        """
        ...

    async def record_request(self, key: str, window_seconds: int) -> None:
        """Record a request for rate limiting."""
        ...
