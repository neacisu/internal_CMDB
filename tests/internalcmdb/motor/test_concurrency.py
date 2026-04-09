"""Tests for motor.concurrency — TokenBucket and try_acquire_within_deadline."""

from __future__ import annotations

import asyncio
import contextlib

import pytest

from internalcmdb.motor.concurrency import TokenBucket, try_acquire_within_deadline


def test_token_bucket_initial_tokens():
    bucket = TokenBucket(max_tokens=10)
    assert bucket.available_tokens == 10
    assert bucket.max_tokens == 10


def test_token_bucket_invalid_max_tokens():
    with pytest.raises(ValueError, match="max_tokens must be"):
        TokenBucket(max_tokens=0)


def test_token_bucket_invalid_refill_rate():
    with pytest.raises(ValueError, match="refill_rate must be"):
        TokenBucket(max_tokens=5, refill_rate=0)


def test_token_bucket_invalid_refill_interval():
    with pytest.raises(ValueError, match="refill_interval must be"):
        TokenBucket(max_tokens=5, refill_interval=0)


@pytest.mark.asyncio
async def test_token_bucket_start_stop():
    bucket = TokenBucket(max_tokens=5)
    await bucket.start()
    with contextlib.suppress(asyncio.CancelledError):
        await bucket.stop()


@pytest.mark.asyncio
async def test_token_bucket_acquire_decrements():
    bucket = TokenBucket(max_tokens=5, refill_rate=100, refill_interval=0.1)
    await bucket.start()
    try:
        before = bucket.available_tokens
        await bucket.acquire()
        after = bucket.available_tokens
        assert after < before
    finally:
        with contextlib.suppress(asyncio.CancelledError):
            await bucket.stop()


@pytest.mark.asyncio
async def test_token_bucket_release_restores():
    bucket = TokenBucket(max_tokens=5)
    await bucket.start()
    try:
        await bucket.acquire()
        before = bucket.available_tokens
        bucket.release()
        after = bucket.available_tokens
        assert after >= before
    finally:
        with contextlib.suppress(asyncio.CancelledError):
            await bucket.stop()


@pytest.mark.asyncio
async def test_token_bucket_max_tokens_not_exceeded():
    bucket = TokenBucket(max_tokens=5, refill_rate=100, refill_interval=0.05)
    await bucket.start()
    try:
        await asyncio.sleep(0.1)
        assert bucket.available_tokens <= bucket.max_tokens
    finally:
        with contextlib.suppress(asyncio.CancelledError):
            await bucket.stop()


@pytest.mark.asyncio
async def test_try_acquire_within_deadline_success():
    bucket = TokenBucket(max_tokens=10, refill_rate=10, refill_interval=0.1)
    await bucket.start()
    try:
        result = await try_acquire_within_deadline(bucket, deadline_seconds=1.0)
        assert result is True
    finally:
        with contextlib.suppress(asyncio.CancelledError):
            await bucket.stop()


@pytest.mark.asyncio
async def test_try_acquire_within_deadline_timeout():
    bucket = TokenBucket(max_tokens=1)
    await bucket.start()
    try:
        await bucket.acquire()
        result = await try_acquire_within_deadline(bucket, deadline_seconds=0.05)
        assert result is False
    finally:
        with contextlib.suppress(asyncio.CancelledError):
            await bucket.stop()
