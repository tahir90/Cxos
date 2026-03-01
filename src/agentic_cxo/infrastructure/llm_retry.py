"""
LLM call wrapper with retries and exponential backoff.

Handles 429 (rate limit), 503 (overloaded), and transient network errors.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _is_retryable(exc: BaseException) -> bool:
    """Check if exception warrants a retry (transient only)."""
    msg = str(exc).lower()
    if "429" in msg or "rate" in msg or "limit" in msg:
        return True
    if "503" in msg or "overloaded" in msg or "capacity" in msg:
        return True
    if "timeout" in msg or "timed out" in msg:
        return True
    if "connection" in msg or "network" in msg:
        return True
    return False


def with_retry(
    fn: Callable[..., T],
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
) -> Callable[..., T]:
    """Wrap an LLM call with retries and exponential backoff."""

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            "LLM call failed (attempt %d): %s",
            retry_state.attempt_number,
            retry_state.outcome.exception() if retry_state.outcome else "?",
        ),
    )
    def _wrapped(*args: Any, **kwargs: Any) -> T:
        return fn(*args, **kwargs)

    return _wrapped
