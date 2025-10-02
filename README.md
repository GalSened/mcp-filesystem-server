# MCP Filesystem Server

Safe-by-default **Model Context Protocol** server for filesystem operations (+ optional command execution).

## Features
- Tools: `list_dir`, `read_text`, `write_text`, `mkdir`, `mv`, `rm`, `stat`
- Optional tool: `run` (disabled by default, allowlist-based, timeout + output cap)
- Transports: **STDIO** (default), **HTTP** (`/mcp`), **SSE`
- Sandbox root with deny/allow globs to protect secrets

## Quickstart (local)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdir -p sandbox
python server.py  # stdio mode

HTTP (for ngrok/cloud)
export MCP_TRANSPORT=http
export MCP_HTTP_PORT=8080
export MCP_HTTP_PATH=/mcp
python server.py
# expose:
ngrok http 8080   # URL -> https://<subdomain>.ngrok.app/mcp

Enable run tool (optional, risky)
export ENABLE_RUN_COMMANDS=1
# edit COMMAND_ALLOWLIST in server.py to expand allowed commands safely

Docker
docker build -t mcp-filesystem .
docker run -p 8080:8080 -e MCP_TRANSPORT=http mcp-filesystem

Connect from ChatGPT (Custom MCP Connector)

Settings → Connectors → Create → Custom

URL: https://YOUR_HOST/mcp (or ngrok URL)

Done. Now you can call the tools from ChatGPT.

Why not GitHub Pages?

GitHub Pages is static hosting only; MCP is an active server (HTTP/SSE/STDIO).
Use Render/Railway/Fly.io/Cloud Run/Cloudflare Workers (or your own machine + ngrok).

Minimal Tool Calls (examples)

list_dir({ "path": ".", "glob_pattern": "*.md" })

read_text({ "path": "README.md" })

write_text({ "path": "demo/hello.txt", "content": "hi" })

mv({ "src": "demo/hello.txt", "dst": "demo/hello2.txt", "overwrite": true })

rm({ "path": "demo", "recursive": true })
