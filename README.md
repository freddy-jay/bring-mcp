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

Nothing to clone — `uvx` fetches and runs it straight from this repository:

```bash
uvx --from git+https://github.com/freddy-jay/bring-mcp bring-mcp
```

## Use it with Claude Code

```bash
claude mcp add bring \
  --env BRING_EMAIL=you@example.com \
  --env BRING_PASSWORD=your-password \
  -- uvx --from git+https://github.com/freddy-jay/bring-mcp bring-mcp
```

## Use it with Claude Desktop

Add this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bring": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/freddy-jay/bring-mcp", "bring-mcp"],
      "env": {
        "BRING_EMAIL": "you@example.com",
        "BRING_PASSWORD": "your-password"
      }
    }
  }
}
```

`uvx` caches the build after the first run. Pin a revision by appending
`@<tag-or-sha>` to the git URL, and pass `--refresh` to pull a newer commit.

## Use it with any other MCP client

The server speaks JSON-RPC over stdio. Point the client at the `uvx` command
above, with `BRING_EMAIL` and `BRING_PASSWORD` set in its environment.

## Run from a local checkout

For hacking on the server:

```bash
git clone https://github.com/freddy-jay/bring-mcp
cd bring-mcp
uv sync
uv run bring-mcp
```

Then give the client `uv --directory /absolute/path/to/bring-mcp run bring-mcp`
as its command instead of the `uvx` form.

## Notes

- The server logs in lazily on the first tool call and reuses the session, so a
  missing or wrong password surfaces as a tool error rather than a startup crash.
- Where several items share a name, pass the `item_uuid` from `get_list_items`
  to `remove_item` or `complete_item` to target one precisely.

## Licence

MIT
