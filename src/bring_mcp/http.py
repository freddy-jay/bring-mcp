"""Streamable HTTP transport, for reaching the server from claude.ai."""

from __future__ import annotations

import hmac
import logging
import os

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .server import mcp

_LOGGER = logging.getLogger(__name__)

ENV_HTTP_TOKEN = "BRING_HTTP_TOKEN"
ENV_HTTP_HOST = "BRING_HTTP_HOST"
ENV_HTTP_PORT = "BRING_HTTP_PORT"
ENV_HTTP_PATH = "BRING_HTTP_PATH"

DEFAULT_HOST = "0.0.0.0"  # noqa: S104 - the container is published on loopback only
DEFAULT_PORT = 8080
DEFAULT_PATH = "/mcp"


class BearerTokenMiddleware:
    """Reject requests that do not carry the expected `Authorization: Bearer` token."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied = ""
        for key, value in scope.get("headers", []):
            if key.lower() == b"authorization":
                supplied = value.decode("latin-1")
                break

        scheme, _, presented = supplied.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(presented, self.token):
            response = PlainTextResponse(
                "Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def build_app(path: str = DEFAULT_PATH, token: str | None = None) -> ASGIApp:
    """Build the ASGI app, wrapping it in bearer auth when a token is configured."""
    app: ASGIApp = mcp.streamable_http_app(
        streamable_http_path=path,
        stateless_http=True,
    )
    if token:
        return BearerTokenMiddleware(app, token)

    _LOGGER.warning(
        "%s is not set: this server is UNAUTHENTICATED. Anyone who can reach it "
        "can read and change the shopping list. Set %s unless the client cannot "
        "send an Authorization header.",
        ENV_HTTP_TOKEN,
        ENV_HTTP_TOKEN,
    )
    return app


def serve(host: str, port: int, path: str) -> None:
    """Serve the MCP endpoint over streamable HTTP."""
    import uvicorn

    token = os.environ.get(ENV_HTTP_TOKEN, "").strip()
    app = build_app(path, token)
    _LOGGER.info("Serving MCP on http://%s:%d%s (auth: %s)", host, port, path,
                 "bearer token" if token else "none")
    uvicorn.run(app, host=host, port=port, log_config=None)
