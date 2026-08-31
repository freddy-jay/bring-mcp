# bring-mcp

An MCP server that lets Claude and other LLM clients read, add to, and clean up
shopping lists on [Bring!](https://www.getbring.com/).

Built on [`miaucl/bring-api`](https://github.com/miaucl/bring-api), an unofficial
Python client for the Bring! API. Not affiliated with or endorsed by Bring! Labs AG.

## Tools

| Tool | What it does |
| --- | --- |
| `get_lists` | Every shopping list on the account, with uuid and name |
| `get_list_items` | Items still to buy plus recently purchased ones |
| `add_item` | Add an item, optionally with a note such as a quantity |
| `remove_item` | Delete an item outright |
| `complete_item` | Tick an item off as purchased |

Item tools take a `list` argument that accepts either the list name (`"Shopping"`)
or its uuid. Omit it to fall back to `BRING_LIST`, or to the only list on the
account when there is just one.

## Configuration

Credentials are read from the environment — nothing is stored in the repository.

| Variable | Required | Purpose |
| --- | --- | --- |
| `BRING_EMAIL` | yes | Bring! account email |
| `BRING_PASSWORD` | yes | Bring! account password |
| `BRING_LIST` | no | Default list name or uuid |
| `BRING_MCP_LOG_LEVEL` | no | `DEBUG`/`INFO`/`WARNING`/`ERROR`, logged to stderr |

Copy `.env.example` to `.env` for local experiments; `.env` is gitignored.

## Install

```bash
git clone https://github.com/freddy-jay/bring-mcp
cd bring-mcp
uv sync
```

## Use it with Claude Code

```bash
claude mcp add bring \
  --env BRING_EMAIL=you@example.com \
  --env BRING_PASSWORD=your-password \
  -- uv --directory /absolute/path/to/bring-mcp run bring-mcp
```

## Use it with Claude Desktop

Add this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bring": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/bring-mcp", "run", "bring-mcp"],
      "env": {
        "BRING_EMAIL": "you@example.com",
        "BRING_PASSWORD": "your-password"
      }
    }
  }
}
```

## Use it with any other MCP client

The server speaks JSON-RPC over stdio. Run `bring-mcp` (or
`uv run bring-mcp`) with `BRING_EMAIL` and `BRING_PASSWORD` set in its
environment, and point the client at that command.

## Notes

- The server logs in lazily on the first tool call and reuses the session, so a
  missing or wrong password surfaces as a tool error rather than a startup crash.
- Where several items share a name, pass the `item_uuid` from `get_list_items`
  to `remove_item` or `complete_item` to target one precisely.

## Licence

MIT
