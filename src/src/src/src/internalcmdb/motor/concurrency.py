"""F3.6 — Concurrency Controls (Token Bucket Rate Limiter).

Provides a :class:`TokenBucket` that rate-limits concurrent async
operations (e.g. LLM API calls) using an ``asyncio.Semaphore``
with configurable refill behaviour.

Important limitations:
    - **Single-process only**: The semaphore-based approach works within
      a single asyncio event loop.  For multi-worker deployments, use a
      Redis-based distributed rate limiter instead.
    - **Non-persistent**: Token state resets on process restart.  This is
      acceptable for rate-limiting but not for quota enforcement.

Usage::

    import contextlib

    bucket = TokenBucket(max_tokens=5, refill_rate=5, refill_interval=1.0)
    await bucket.start()           # begin background refill
    acquired = False
    try:
        async with asyncio.timeout(30.0):
            await bucket.acquire()
        acquired = True
        response = await call_llm(…)
    except TimeoutError:
        pass  # no token within 30s — log or metric as needed
    finally:
        if acquired:
            bucket.release()
        with contextlib.suppress(asyncio.CancelledError):
            await bucket.stop()
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class TokenBucket:
    """Async token-bucket rate limiter backed by :class:`asyncio.Semaphore`.

    Parameters
    ----------
    max_tokens:
        Maximum number of concurrent tokens (burst capacity).
    refill_rate:
        Number of tokens added per refill cycle.
    refill_interval:
        Seconds between refill cycles.
    """

    def __init__(
        self,
        max_tokens: int = 5,
        refill_rate: int = 5,
        refill_interval: float = 1.0,
    ) -> None:
        if max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if refill_rate < 1:
            raise ValueError("refill_rate must be >= 1")
        if refill_interval <= 0:
            raise ValueError("refill_interval must be > 0")

        self._max_tokens = max_tokens
        self._refill_rate = refill_rate
        self._refill_interval = refill_interval

        self._semaphore = asyncio.Semaphore(max_tokens)
        self._current_tokens = max_tokens
        self._refill_task: asyncio.Task[None] | None = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background refill loop."""
        if self._running:
            return
        self._running = True
        self._refill_task = asyncio.create_task(self._refill_loop())
        await asyncio.sleep(0)
        logger.info(
            "TokenBucket started: max=%d refill=%d/%0.1fs",
            self._max_tokens,
            self._refill_rate,
            self._refill_interval,
        )

    async def stop(self) -> None:
        """Stop the background refill loop.

        If the refill task is cancelled, :exc:`asyncio.CancelledError` is
        propagated after local cleanup so cancellation semantics stay correct.
        In a bare ``finally:`` block where propagation is undesirable, wrap the
        call with ``contextlib.suppress(asyncio.CancelledError)``.
        """
        self._running = False
        task = self._refill_task
        self._refill_task = None
        if task is None:
            logger.info("TokenBucket stopped.")
            return

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.debug("TokenBucket refill task cancelled.")
            raise
        logger.info("TokenBucket stopped.")

    # ------------------------------------------------------------------
    # Token operations
    # ------------------------------------------------------------------

    async def acquire(self) -> None:
        """Block until a token is granted (see semaphore semantics).

        For a wall-clock bound, compose at the call site::

            async with asyncio.timeout(30.0):
                await bucket.acquire()

        which raises :exc:`TimeoutError` when the deadline is exceeded.
        """
        await self._semaphore.acquire()
        self._current_tokens -= 1

    def release(self) -> None:
        """Return a token to the bucket (up to max_tokens)."""
        if self._current_tokens < self._max_tokens:
            self._semaphore.release()
            self._current_tokens += 1

    @property
    def available_tokens(self) -> int:
        return self._current_tokens

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    # ------------------------------------------------------------------
    # Background refill
    # ------------------------------------------------------------------

    async def _refill_loop(self) -> None:
        """Periodically refill tokens up to max_tokens."""
        try:
            while self._running:
                await asyncio.sleep(self._refill_interval)
                refilled = 0
                for _ in range(self._refill_rate):
                    if self._current_tokens >= self._max_tokens:
                        break
                    self._semaphore.release()
                    self._current_tokens += 1
                    refilled += 1
                if refilled:
                    logger.debug(
                        "TokenBucket refilled %d token(s). available=%d",
                        refilled,
                        self._current_tokens,
                    )
        except asyncio.CancelledError:
            logger.debug("TokenBucket refill loop exiting on cancel.")
            raise


async def try_acquire_within_deadline(
    bucket: TokenBucket,
    *,
    deadline_seconds: float,
) -> bool:
    """Acquire a token before *deadline_seconds* elapse.

    Returns ``True`` on success, ``False`` on :exc:`TimeoutError`.
    Implemented with :func:`asyncio.timeout` at this boundary so call sites
    that need a boolean do not duplicate try/except boilerplate.

    For full control, prefer ``async with asyncio.timeout(...): await bucket.acquire()``.
    """
    try:
        async with asyncio.timeout(deadline_seconds):
            await bucket.acquire()
        return True
    except TimeoutError:
        logger.debug(
            "TokenBucket not acquired within %.1fs",
            deadline_seconds,
        )
        return False
