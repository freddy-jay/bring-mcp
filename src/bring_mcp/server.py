"""MCP server exposing Bring! shopping list operations to LLM clients."""

from __future__ import annotations

import logging
import os
from importlib.metadata import version
from typing import Any

from bring_api import Bring
from bring_api.exceptions import BringException, BringMissingFieldException
from mcp.server.mcpserver import MCPServer

from .client import ConfigurationError, with_retry

_LOGGER = logging.getLogger(__name__)

_ENV_DEFAULT_LIST = "BRING_LIST"

mcp = MCPServer(
    name="bring",
    version=version("bring-mcp"),
    instructions=(
        "Manage Bring! shopping lists. Call `get_lists` first to discover the "
        "available lists, then pass either the list name or its uuid to the item "
        "tools. If BRING_LIST is configured, the `list` argument may be omitted "
        "and the default list is used. Use `remove_item` to delete an item "
        "outright and `complete_item` to tick it off as purchased."
    ),
)


class ListNotFoundError(RuntimeError):
    """Raised when a list name or uuid cannot be resolved."""


_HANDLED = (
    BringException,
    BringMissingFieldException,
    ConfigurationError,
    ListNotFoundError,
)


async def _resolve_list(bring: Bring, list: str | None) -> str:
    """Resolve a list name, uuid, or the configured default to a list uuid."""
    wanted = (list or os.environ.get(_ENV_DEFAULT_LIST, "")).strip()
    lists = (await bring.load_lists()).lists

    if not wanted:
        if len(lists) == 1:
            return lists[0].listUuid
        names = ", ".join(f"{item.name!r}" for item in lists)
        raise ListNotFoundError(
            f"No list specified. Available lists: {names}. Pass one as `list`, "
            f"or set {_ENV_DEFAULT_LIST} to make it the default."
        )

    for item in lists:
        if item.listUuid == wanted:
            return item.listUuid
    for item in lists:
        if item.name.casefold() == wanted.casefold():
            return item.listUuid

    names = ", ".join(f"{item.name!r}" for item in lists)
    raise ListNotFoundError(f"No list named {wanted!r}. Available lists: {names}.")


def _fail(action: str, exc: Exception) -> dict[str, Any]:
    """Turn an exception into a result the model can act on."""
    _LOGGER.debug("%s failed", action, exc_info=True)
    return {"ok": False, "error": f"{action} failed: {exc}"}


@mcp.tool()
async def get_lists() -> dict[str, Any]:
    """List every Bring! shopping list on the account, with its uuid and name."""
    try:
        response = await with_retry(lambda bring: bring.load_lists())
    except _HANDLED as exc:
        return _fail("Loading shopping lists", exc)

    return {
        "ok": True,
        "lists": [
            {"uuid": item.listUuid, "name": item.name} for item in response.lists
        ],
        "default": os.environ.get(_ENV_DEFAULT_LIST) or None,
    }


@mcp.tool()
async def get_list_items(list: str | None = None) -> dict[str, Any]:
    """Get the items on a shopping list.

    Args:
        list: List name or uuid. Omit to use the BRING_LIST default.

    Returns items still to buy plus recently purchased ones. Each item carries a
    `uuid` that can be passed back to `remove_item` or `complete_item` to target
    that exact item when several share a name.
    """

    async def call(bring: Bring) -> dict[str, Any]:
        list_uuid = await _resolve_list(bring, list)
        items = (await bring.get_list(list_uuid)).items
        return {
            "ok": True,
            "list_uuid": list_uuid,
            "purchase": [
                {
                    "uuid": item.uuid,
                    "name": item.itemId,
                    "specification": item.specification,
                }
                for item in items.purchase
            ],
            "recently": [
                {
                    "uuid": item.uuid,
                    "name": item.itemId,
                    "specification": item.specification,
                }
                for item in items.recently
            ],
        }

    try:
        return await with_retry(call)
    except _HANDLED as exc:
        return _fail("Reading the shopping list", exc)


@mcp.tool()
async def add_item(
    item: str,
    specification: str = "",
    list: str | None = None,
) -> dict[str, Any]:
    """Add an item to a shopping list, or update the note on an existing one.

    Args:
        item: Item name, e.g. "Milk".
        specification: Optional note such as a quantity or brand, e.g. "2 litres".
        list: List name or uuid. Omit to use the BRING_LIST default.
    """

    async def call(bring: Bring) -> dict[str, Any]:
        list_uuid = await _resolve_list(bring, list)
        await bring.save_item(list_uuid, item, specification)
        return {"ok": True, "list_uuid": list_uuid, "added": item}

    try:
        return await with_retry(call)
    except _HANDLED as exc:
        return _fail(f"Adding {item!r}", exc)


@mcp.tool()
async def remove_item(
    item: str,
    list: str | None = None,
    item_uuid: str | None = None,
) -> dict[str, Any]:
    """Delete an item from a shopping list without marking it as purchased.

    Args:
        item: Item name, e.g. "Milk".
        list: List name or uuid. Omit to use the BRING_LIST default.
        item_uuid: Optional item uuid from `get_list_items`, to pick one of
            several items sharing a name. Without it the oldest match is removed.
    """

    async def call(bring: Bring) -> dict[str, Any]:
        list_uuid = await _resolve_list(bring, list)
        await bring.remove_item(list_uuid, item, item_uuid)
        return {"ok": True, "list_uuid": list_uuid, "removed": item}

    try:
        return await with_retry(call)
    except _HANDLED as exc:
        return _fail(f"Removing {item!r}", exc)


@mcp.tool()
async def complete_item(
    item: str,
    list: str | None = None,
    item_uuid: str | None = None,
) -> dict[str, Any]:
    """Tick an item off as purchased, moving it to the recently-bought section.

    Args:
        item: Item name, e.g. "Milk".
        list: List name or uuid. Omit to use the BRING_LIST default.
        item_uuid: Optional item uuid from `get_list_items`, to pick one of
            several items sharing a name.
    """

    async def call(bring: Bring) -> dict[str, Any]:
        list_uuid = await _resolve_list(bring, list)
        await bring.complete_item(list_uuid, item, item_uuid=item_uuid)
        return {"ok": True, "list_uuid": list_uuid, "completed": item}

    try:
        return await with_retry(call)
    except _HANDLED as exc:
        return _fail(f"Completing {item!r}", exc)
