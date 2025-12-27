"""
Rate limiting for authentication endpoints.

Prevents brute force attacks and abuse by limiting:
- Login attempts
- OTP requests
- Password reset requests
- API calls per user/IP
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int):
        """
        Initialize rate limit exception.

        Args:
            retry_after: Seconds until limit resets
        """
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after} seconds.")


class RateLimiter:
    """In-memory rate limiter for authentication operations."""

    def __init__(self):
        """Initialize rate limiter."""
        # Storage: identifier -> (attempts, first_attempt_time, blocked_until)
        self._limits: Dict[str, Tuple[int, float, Optional[float]]] = {}

        # Rate limit configurations
        self.limits = {
            "login": {
                "max_attempts": 5,
                "window_seconds": 900,  # 15 minutes
                "block_seconds": 3600  # 1 hour
            },
            "2fa": {
                "max_attempts": 3,
                "window_seconds": 300,  # 5 minutes
                "block_seconds": 1800  # 30 minutes
            },
            "password_reset": {
                "max_attempts": 3,
                "window_seconds": 3600,  # 1 hour
                "block_seconds": 7200  # 2 hours
            },
            "otp_send": {
                "max_attempts": 5,
                "window_seconds": 3600,  # 1 hour
                "block_seconds": 3600  # 1 hour
            },
            "api_call": {
                "max_attempts": 100,
                "window_seconds": 60,  # 1 minute
                "block_seconds": 300  # 5 minutes
            }
        }

    def check_rate_limit(
        self,
        identifier: str,
        limit_type: str = "api_call"
    ) -> Tuple[bool, int]:
        """
        Check if rate limit is exceeded.

        Args:
            identifier: Unique identifier (IP address, user_id, etc.)
            limit_type: Type of rate limit to check

        Returns:
            Tuple of (is_allowed, remaining_attempts)

        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        if limit_type not in self.limits:
            logger.warning(f"Unknown rate limit type: {limit_type}")
            return True, 0

        config = self.limits[limit_type]
        key = f"{limit_type}:{identifier}"
        now = time.time()

        # Get or create limit record
        if key not in self._limits:
            self._limits[key] = (0, now, None)

        attempts, first_attempt, blocked_until = self._limits[key]

        # Check if blocked
        if blocked_until and now < blocked_until:
            retry_after = int(blocked_until - now)
            logger.warning(
                f"Rate limit blocked: {limit_type} for {identifier}, "
                f"retry after {retry_after}s"
            )
            raise RateLimitExceeded(retry_after)

        # Reset if window expired
        if now - first_attempt > config["window_seconds"]:
            self._limits[key] = (0, now, None)
            attempts = 0

        remaining = config["max_attempts"] - attempts

        if remaining <= 0:
            # Block for configured duration
            blocked_until = now + config["block_seconds"]
            self._limits[key] = (attempts, first_attempt, blocked_until)

            retry_after = config["block_seconds"]
            logger.warning(
                f"Rate limit exceeded: {limit_type} for {identifier}, "
                f"blocking for {retry_after}s"
            )
            raise RateLimitExceeded(retry_after)

        return True, remaining

    def record_attempt(
        self,
        identifier: str,
        limit_type: str = "api_call",
        success: bool = False
    ) -> int:
        """
        Record an attempt.

        Args:
            identifier: Unique identifier
            limit_type: Type of rate limit
            success: Whether attempt was successful

        Returns:
            Remaining attempts
        """
        if limit_type not in self.limits:
            return 0

        config = self.limits[limit_type]
        key = f"{limit_type}:{identifier}"
        now = time.time()

        # Get current state
        if key not in self._limits:
            self._limits[key] = (0, now, None)

        attempts, first_attempt, blocked_until = self._limits[key]

        # If successful, reset counter (for login/2fa)
        if success and limit_type in ["login", "2fa"]:
            self._limits[key] = (0, now, None)
            logger.info(f"Rate limit reset for {limit_type}:{identifier} after success")
            return config["max_attempts"]

        # Increment attempt counter
        attempts += 1
        self._limits[key] = (attempts, first_attempt, blocked_until)

        remaining = config["max_attempts"] - attempts

        logger.debug(
            f"Rate limit recorded: {limit_type}:{identifier}, "
            f"attempts={attempts}, remaining={remaining}"
        )

        return remaining

    def reset(self, identifier: str, limit_type: str = "api_call") -> None:
        """
        Reset rate limit for identifier.

        Args:
            identifier: Unique identifier
            limit_type: Type of rate limit
        """
        key = f"{limit_type}:{identifier}"

        if key in self._limits:
            del self._limits[key]
            logger.info(f"Rate limit reset: {limit_type}:{identifier}")

    def get_status(
        self,
        identifier: str,
        limit_type: str = "api_call"
    ) -> Dict:
        """
        Get rate limit status for identifier.

        Args:
            identifier: Unique identifier
            limit_type: Type of rate limit

        Returns:
            Dictionary with rate limit status
        """
        if limit_type not in self.limits:
            return {}

        config = self.limits[limit_type]
        key = f"{limit_type}:{identifier}"
        now = time.time()

        if key not in self._limits:
            return {
                "attempts": 0,
                "remaining": config["max_attempts"],
                "blocked": False,
                "retry_after": 0
            }

        attempts, first_attempt, blocked_until = self._limits[key]

        # Check if window expired
        if now - first_attempt > config["window_seconds"]:
            return {
                "attempts": 0,
                "remaining": config["max_attempts"],
                "blocked": False,
                "retry_after": 0
            }

        blocked = blocked_until is not None and now < blocked_until
        retry_after = int(blocked_until - now) if blocked else 0
        remaining = max(0, config["max_attempts"] - attempts)

        return {
            "attempts": attempts,
            "remaining": remaining,
            "blocked": blocked,
            "retry_after": retry_after
        }

    def cleanup_expired(self) -> int:
        """
        Remove expired rate limit records.

        Returns:
            Number of records removed
        """
        now = time.time()
        expired_keys = []

        for key, (attempts, first_attempt, blocked_until) in self._limits.items():
            limit_type = key.split(":", 1)[0]

            if limit_type not in self.limits:
                expired_keys.append(key)
                continue

            config = self.limits[limit_type]

            # Remove if window expired and not blocked
            if (now - first_attempt > config["window_seconds"] and
                (not blocked_until or now > blocked_until)):
                expired_keys.append(key)

        for key in expired_keys:
            del self._limits[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired rate limit records")

        return len(expired_keys)


# Global rate limiter instance
_rate_limiter = None


def get_rate_limiter() -> RateLimiter:
    """
    Get global rate limiter instance.

    Returns:
        Rate limiter instance
    """
    global _rate_limiter

    if _rate_limiter is None:
        _rate_limiter = RateLimiter()

    return _rate_limiter
