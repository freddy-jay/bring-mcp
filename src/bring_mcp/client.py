"""Lazy, single-instance Bring! API client backed by environment credentials."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from typing import TypeVar

import aiohttp
import keyring
from bring_api import Bring, BringAuthException
from keyring.errors import KeyringError

T = TypeVar("T")

ENV_EMAIL = "BRING_EMAIL"
ENV_PASSWORD = "BRING_PASSWORD"
ENV_KEYRING_SERVICE = "BRING_KEYRING_SERVICE"

DEFAULT_KEYRING_SERVICE = "bring-mcp"

_lock = asyncio.Lock()
_session: aiohttp.ClientSession | None = None
_bring: Bring | None = None


class ConfigurationError(RuntimeError):
    """Raised when the required credentials are missing from the environment."""


def keyring_service() -> str:
    """Name the credential-store service entry the password is filed under."""
    return os.environ.get(ENV_KEYRING_SERVICE, "").strip() or DEFAULT_KEYRING_SERVICE


def stored_password(mail: str) -> str | None:
    """Read the password for `mail` from the OS credential store, if present.

    On Windows this is Credential Manager; keyring picks the platform-native
    backend elsewhere. A store that is unavailable is treated as empty so the
    environment variable can still be used.
    """
    try:
        return keyring.get_password(keyring_service(), mail)
    except KeyringError:
        return None


def credentials() -> tuple[str, str]:
    """Resolve the Bring! credentials, preferring the environment over the vault."""
    mail = os.environ.get(ENV_EMAIL, "").strip()
    if not mail:
        raise ConfigurationError(
            f"Missing environment variable {ENV_EMAIL}. Set it in the MCP server "
            "configuration to the email address of the Bring! account."
        )

    password = os.environ.get(ENV_PASSWORD, "") or stored_password(mail) or ""
    if not password:
        raise ConfigurationError(
            f"No password found for {mail}. Either store one in the OS credential "
            f"store with `bring-mcp set-password` (service {keyring_service()!r}), "
            f"or set {ENV_PASSWORD} in the MCP server configuration."
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
