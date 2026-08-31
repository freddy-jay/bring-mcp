"""Lazy, single-instance Bring! API client backed by environment credentials."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from typing import TypeVar

import aiohttp
from bring_api import Bring, BringAuthException

T = TypeVar("T")

_ENV_EMAIL = "BRING_EMAIL"
_ENV_PASSWORD = "BRING_PASSWORD"

_lock = asyncio.Lock()
_session: aiohttp.ClientSession | None = None
_bring: Bring | None = None


class ConfigurationError(RuntimeError):
    """Raised when the required credentials are missing from the environment."""


def credentials() -> tuple[str, str]:
    """Read the Bring! credentials from the environment."""
    mail = os.environ.get(_ENV_EMAIL, "").strip()
    password = os.environ.get(_ENV_PASSWORD, "")
    missing = [
        name
        for name, value in ((_ENV_EMAIL, mail), (_ENV_PASSWORD, password))
        if not value
    ]
    if missing:
        raise ConfigurationError(
            f"Missing environment variable(s): {', '.join(missing)}. "
            f"Set {_ENV_EMAIL} and {_ENV_PASSWORD} in the MCP server configuration."
        )
    return mail, password


async def get_client() -> Bring:
    """Return the logged-in Bring! client, creating and authenticating it once."""
    global _session, _bring

    async with _lock:
        if _bring is not None:
            return _bring

        mail, password = credentials()
        if _session is None or _session.closed:
            _session = aiohttp.ClientSession()
        bring = Bring(_session, mail, password)
        await bring.login()
        _bring = bring
        return _bring


async def reset_client() -> None:
    """Drop the cached client so the next call re-authenticates."""
    global _bring
    async with _lock:
        _bring = None


async def with_retry(call: Callable[[Bring], Awaitable[T]]) -> T:
    """Run an API call, re-authenticating once if the session has expired."""
    bring = await get_client()
    try:
        return await call(bring)
    except BringAuthException:
        await reset_client()
        bring = await get_client()
        return await call(bring)


async def close() -> None:
    """Close the shared HTTP session."""
    global _session, _bring
    _bring = None
    if _session is not None and not _session.closed:
        await _session.close()
    _session = None
