"""MCP server for the Bring! shopping list API."""

from .cli import main
from .server import mcp

__all__ = ["main", "mcp"]
