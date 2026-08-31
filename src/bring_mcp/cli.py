"""Command line entry point: run the server, or manage the stored password."""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import sys

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from .client import ENV_EMAIL, keyring_service
from .http import (
    DEFAULT_HOST,
    DEFAULT_PATH,
    DEFAULT_PORT,
    ENV_HTTP_HOST,
    ENV_HTTP_PATH,
    ENV_HTTP_PORT,
)
from .http import serve as serve_http
from .server import mcp


def _email(args: argparse.Namespace) -> str:
    """Take the account email from the flag, the environment, or a prompt."""
    mail = (args.email or os.environ.get(ENV_EMAIL, "")).strip()
    if not mail:
        mail = input("Bring! email: ").strip()
    if not mail:
        raise SystemExit(f"No email given. Pass --email or set {ENV_EMAIL}.")
    return mail


def _set_password(args: argparse.Namespace) -> None:
    """Store the Bring! password in the OS credential store."""
    mail = _email(args)
    password = getpass.getpass(f"Bring! password for {mail}: ")
    if not password:
        raise SystemExit("No password given, nothing stored.")
    keyring.set_password(keyring_service(), mail, password)
    print(f"Stored the password for {mail} under service {keyring_service()!r}.")


def _delete_password(args: argparse.Namespace) -> None:
    """Remove the stored password."""
    mail = _email(args)
    try:
        keyring.delete_password(keyring_service(), mail)
    except PasswordDeleteError:
        print(f"No stored password for {mail}.")
    else:
        print(f"Deleted the stored password for {mail}.")


def _status(args: argparse.Namespace) -> None:
    """Report which backend is in use and whether a password is stored."""
    print(f"Credential store: {keyring.get_keyring()}")
    print(f"Service:          {keyring_service()}")
    mail = (args.email or os.environ.get(ENV_EMAIL, "")).strip()
    if not mail:
        print(f"Email:            not set (pass --email or set {ENV_EMAIL})")
        return
    print(f"Email:            {mail}")
    print(f"Password stored:  {keyring.get_password(keyring_service(), mail) is not None}")


def _configure_logging() -> None:
    """Send logs to stderr; stdout carries the JSON-RPC framing on stdio."""
    logging.basicConfig(
        stream=sys.stderr,
        level=os.environ.get("BRING_MCP_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _serve_stdio(_: argparse.Namespace) -> None:
    """Run the MCP server over stdio, for a client that launches it as a subprocess."""
    _configure_logging()
    mcp.run(transport="stdio")


def _serve_http(args: argparse.Namespace) -> None:
    """Run the MCP server over streamable HTTP, for a remote client such as claude.ai."""
    _configure_logging()
    host = args.host or os.environ.get(ENV_HTTP_HOST) or DEFAULT_HOST
    port = args.port or int(os.environ.get(ENV_HTTP_PORT) or DEFAULT_PORT)
    path = args.path or os.environ.get(ENV_HTTP_PATH) or DEFAULT_PATH
    serve_http(host, port, path)


def main() -> None:
    """Dispatch to a subcommand, defaulting to running the server."""
    parser = argparse.ArgumentParser(
        prog="bring-mcp",
        description="MCP server for Bring! shopping lists. "
        "Run without arguments to serve over stdio.",
    )
    parser.set_defaults(handler=_serve_stdio, email=None)
    subcommands = parser.add_subparsers()

    for name, handler, help_text in (
        ("set-password", _set_password, "Store the Bring! password in the OS credential store"),
        ("delete-password", _delete_password, "Remove the stored Bring! password"),
        ("status", _status, "Show the credential store backend and whether a password is stored"),
    ):
        sub = subcommands.add_parser(name, help=help_text)
        sub.add_argument("--email", help=f"Bring! account email (default: ${ENV_EMAIL})")
        sub.set_defaults(handler=handler)

    http = subcommands.add_parser(
        "serve-http",
        help="Serve over streamable HTTP instead of stdio, for remote clients",
    )
    http.add_argument("--host", help=f"Interface to bind (default: {DEFAULT_HOST})")
    http.add_argument("--port", type=int, help=f"Port to bind (default: {DEFAULT_PORT})")
    http.add_argument("--path", help=f"MCP endpoint path (default: {DEFAULT_PATH})")
    http.set_defaults(handler=_serve_http)

    args = parser.parse_args()
    try:
        args.handler(args)
    except KeyringError as exc:
        raise SystemExit(f"Credential store unavailable: {exc}") from exc
