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

Credentials are read from the environment or the OS credential store — nothing is
stored in the repository.

| Variable | Required | Purpose |
| --- | --- | --- |
| `BRING_EMAIL` | yes | Bring! account email |
| `BRING_PASSWORD` | unless stored in the credential store | Bring! account password |
| `BRING_LIST` | no | Default list name or uuid |
| `BRING_KEYRING_SERVICE` | no | Credential store service name (default `bring-mcp`) |
| `BRING_MCP_LOG_LEVEL` | no | `DEBUG`/`INFO`/`WARNING`/`ERROR`, logged to stderr |

`BRING_PASSWORD` wins when both are set. Copy `.env.example` to `.env` for local
experiments; `.env` is gitignored.

### Keep the password out of the client config

Putting `BRING_PASSWORD` in `claude_desktop_config.json` or `~/.claude.json`
leaves it in plaintext on disk. Store it in Windows Credential Manager instead
(macOS Keychain and the Secret Service on Linux work the same way):

```bash
uvx --from git+https://github.com/freddy-jay/bring-mcp bring-mcp set-password --email you@example.com
```

The password is prompted for, never passed as an argument, so it stays out of
your shell history. Then give the client only `BRING_EMAIL`, and the server
looks the password up on each login.

```bash
bring-mcp status           # which backend is in use, and whether a password is stored
bring-mcp delete-password  # remove it again
```

## Install

Install it once as a tool, so launching the server never touches the network:

```bash
uv tool install git+https://github.com/freddy-jay/bring-mcp
```

That puts a `bring-mcp` executable on your PATH:

| Platform | Path |
| --- | --- |
| macOS / Linux | `~/.local/bin/bring-mcp` |
| Windows | `%USERPROFILE%\.local\bin\bring-mcp.exe` |

Upgrade later with `uv tool upgrade bring-mcp`.

Use the **absolute path** in every MCP client config below. Desktop apps launch
their servers with a minimal PATH, so a bare `bring-mcp` may not resolve.

## Use it with Claude Code

```bash
claude mcp add bring \
  --env BRING_EMAIL=you@example.com \
  -- ~/.local/bin/bring-mcp
```

## Use it with Claude Desktop

Add this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bring": {
      "command": "/Users/you/.local/bin/bring-mcp",
      "args": [],
      "env": {
        "BRING_EMAIL": "you@example.com",
        "BRING_LIST": "Shopping"
      }
    }
  }
}
```

On Windows the command is `C:\\Users\\you\\.local\\bin\\bring-mcp.exe`
(JSON needs the doubled backslashes).

## Use it with any other MCP client

The server speaks JSON-RPC over stdio. Point the client at the installed
executable with at least `BRING_EMAIL` set in its environment.

## Trying it without installing

`uvx` can run it straight from the repository:

```bash
uvx --from git+https://github.com/freddy-jay/bring-mcp bring-mcp
```

This is fine for a quick look from a terminal, but **don't put it in a client
config**: `uvx` re-resolves the git URL on every launch, so it needs `git` on
PATH and a working network at startup. Claude Desktop launches servers with a
minimal PATH, where `git` usually isn't visible, and the server dies with
`Git executable not found` before it can speak. `uv tool install` avoids this
entirely.

## Run from a local checkout

For hacking on the server:

```bash
git clone https://github.com/freddy-jay/bring-mcp
cd bring-mcp
uv sync
uv run bring-mcp
```

`uv tool install --editable /path/to/bring-mcp` installs that checkout instead,
so a `git pull` takes effect without reinstalling.

## Notes

- The server logs in lazily on the first tool call and reuses the session, so a
  missing or wrong password surfaces as a tool error rather than a startup crash.
- Bring! authenticates with email and password only; there is no API token to
  scope or revoke, which is why the credential store is worth the extra step.
- Where several items share a name, pass the `item_uuid` from `get_list_items`
  to `remove_item` or `complete_item` to target one precisely.

## Licence

MIT
