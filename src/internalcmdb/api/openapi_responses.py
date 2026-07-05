"""Shared OpenAPI response schemas for FastAPI route decorators."""

from __future__ import annotations

RESP_400: dict[int, dict[str, str]] = {400: {"description": "Bad request"}}
RESP_401: dict[int, dict[str, str]] = {401: {"description": "Unauthorized"}}
RESP_403: dict[int, dict[str, str]] = {403: {"description": "Forbidden"}}
RESP_404: dict[int, dict[str, str]] = {404: {"description": "Not found"}}
RESP_409: dict[int, dict[str, str]] = {409: {"description": "Conflict"}}
RESP_422: dict[int, dict[str, str]] = {422: {"description": "Unprocessable entity"}}
RESP_500: dict[int, dict[str, str]] = {500: {"description": "Internal server error"}}
RESP_503: dict[int, dict[str, str]] = {503: {"description": "Service unavailable"}}


def merge_responses(*parts: dict[int, dict[str, str]]) -> dict[int, dict[str, str]]:
    """Merge multiple response dicts for FastAPI ``responses=``."""
    merged: dict[int, dict[str, str]] = {}
    for part in parts:
        merged.update(part)
    return merged
