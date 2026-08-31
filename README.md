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
| `BRING_HTTP_TOKEN` | no | Bearer token required by `serve-http` (see below) |
| `BRING_HTTP_HOST` / `BRING_HTTP_PORT` / `BRING_HTTP_PATH` | no | `serve-http` bind address, defaults `0.0.0.0`, `8080`, `/mcp` |

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
        "BRING_EMAIL": "you@example.com"
      }
    }
  }
}
```

`uvx` caches the build after the first run. Pin a revision by appending
`@<tag-or-sha>` to the git URL, and pass `--refresh` to pull a newer commit.

## Use it with any other MCP client

The server speaks JSON-RPC over stdio. Point the client at the `uvx` command
above, with at least `BRING_EMAIL` set in its environment.

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

## Self-host it for claude.ai

`bring-mcp serve-http` speaks the same MCP over streamable HTTP, so claude.ai can
use it as a custom connector. Anthropic connects **from its own servers**, so the
endpoint has to be reachable on the public internet — a plain Tailscale tailnet is
not enough, and Tailscale Funnel is what bridges the gap.

### 1. Run the container

```bash
git clone https://github.com/freddy-jay/bring-mcp
cd bring-mcp
podman build -t bring-mcp .
```

Put the credentials in a file readable only by you, rather than on the command
line where they land in your shell history and `podman inspect`:

```bash
install -m 600 /dev/null ~/bring.env
cat > ~/bring.env <<'ENV'
BRING_EMAIL=you@example.com
BRING_PASSWORD=your-password
BRING_LIST=Shopping
ENV
```

```bash
podman run -d --name bring-mcp --restart=always \
  -p 127.0.0.1:8080:8080 \
  --env-file ~/bring.env \
  bring-mcp
```

The image runs as an unprivileged user and binds `0.0.0.0` *inside* the container;
publishing it on `127.0.0.1` keeps it off your LAN. Check it:

```bash
curl -s -X POST http://127.0.0.1:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

The OS credential store is unavailable inside a container, so the container path
uses `BRING_PASSWORD`. `bring-mcp set-password` is for host installs.

To keep it running across reboots, generate a unit:
`podman generate systemd --new --name bring-mcp > ~/.config/systemd/user/bring-mcp.service`,
then `systemctl --user enable --now bring-mcp` and `loginctl enable-linger $USER`.

### 2. Expose it with Tailscale Funnel

Funnel publishes a single local port on your node's public `*.ts.net` name, with a
real certificate. Funnel listens on 443, 8443 or 10000 — 8080 below is the *local*
port it forwards to:

```bash
tailscale funnel --bg 8080
tailscale funnel status
```

Your connector URL is the node's name plus the MCP path:

```
https://your-node.your-tailnet.ts.net/mcp
```

Funnel needs the `funnel` node attribute in your tailnet policy file and MagicDNS
enabled; `tailscale funnel` prints a link to grant it the first time.

### 3. Add it in claude.ai

Settings → Connectors → **Add custom connector**, paste the URL above, and connect.
Then ask Claude to add something to your list.

### Locking it down

Claude reaches Funnel from the public internet, and Funnel does not pass the caller's
IP to your container, so an IP allowlist can't work here. That leaves two options:

- **Authless** (leave `BRING_HTTP_TOKEN` unset). Works with claude.ai today. The
  server logs a warning at startup. Note that Funnel hostnames appear in public
  Certificate Transparency logs, so treat the URL as discoverable, not secret —
  anyone who finds it can read and edit the list.
- **Bearer token** (`BRING_HTTP_TOKEN=$(openssl rand -hex 32)`). Every request
  without a matching `Authorization: Bearer` header gets a 401. claude.ai only
  sends custom headers under Anthropic's `static_headers` beta, so this works today
  from Claude Code and Claude Desktop and needs that beta on claude.ai:

  ```bash
  claude mcp add --transport http bring https://your-node.your-tailnet.ts.net/mcp \
    --header "Authorization: Bearer $BRING_HTTP_TOKEN"
  ```

Either way the server holds one Bring! account, so everyone who can reach the URL
acts as you. Turn the Funnel off with `tailscale funnel --https=443 off`.

## Notes

- The server logs in lazily on the first tool call and reuses the session, so a
  missing or wrong password surfaces as a tool error rather than a startup crash.
- Bring! authenticates with email and password only; there is no API token to
  scope or revoke, which is why the credential store is worth the extra step.
- Where several items share a name, pass the `item_uuid` from `get_list_items`
  to `remove_item` or `complete_item` to target one precisely.
- `serve-http` runs stateless, so it survives restarts and sits behind a proxy
  without session affinity.

## Licence

MIT
