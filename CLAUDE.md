# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

An MCP (Model Context Protocol) server for Monarch Money personal finance. Wraps the `monarchmoney` Python SDK with 40+ tools exposed via FastMCP. Runs in two modes: **stdio** (local, for Claude Desktop) and **HTTP/SSE** (remote, for Claude mobile and other clients). Deployed to Google Cloud Run via GitHub Actions CD.

## Commands

```bash
# Install (uses uv for dependency management)
uv sync --extra dev

# Run all tests
uv run pytest tests/ -v

# Run a single test file / single test
uv run pytest tests/test_safety.py -v
uv run pytest tests/test_transaction_tools.py::test_name -v

# Lint + format check
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Auto-fix lint issues
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/

# Type check (uses ty, not mypy)
uv run ty check src/

# Run stdio server locally
uv run monarch-mcp-server

# Run HTTP server locally (requires auth env vars)
uv run monarch-mcp-http
```

## Architecture

### Two Server Modes

- **`server.py`** — Stdio MCP server for local use. Creates a `FastMCP` instance, registers tools, runs with `show_banner=False` to keep stdout clean for JSON-RPC.
- **`http_server.py`** — HTTP/SSE server for remote use. Starlette ASGI app with three possible MCP mounts depending on `MCP_AUTH_MODE`:
  - `token` (default): Single bearer-token auth on `/mcp`
  - `oauth`: GitHub OAuth on `/mcp`
  - `both`: OAuth on `/mcp` + token on `/mcp-token/mcp`
  - Optional CI smoke endpoint at `/mcp-smoke/mcp` (when `MCP_ENABLE_CI_SMOKE=true`)

### Tool Registration Pattern

Tools live in `src/monarch_mcp_server/tools/`, one file per domain (accounts, transactions, budgets, categories, tags, metadata, refresh, safety). Each module exports a `register_<domain>_tools(mcp: FastMCP)` function. The `tools/__init__.py` coordinator calls all of them.

Every tool function follows a consistent decorator stack:
```python
@mcp.tool()
@require_safety_check("operation_name")  # only for write operations
@tool_handler("operation_name")          # error handling + session auto-retry
async def some_tool(...) -> dict:
    client = await get_monarch_client()
    ...
```

**Decorator order matters**: `@mcp.tool()` outermost, then `@require_safety_check` (for writes), then `@tool_handler` innermost. The `tool_handler` catches exceptions, formats errors, and retries once on auth failures by invalidating the cached session.

### Authentication Flow (`client.py` + `secure_session.py`)

`get_monarch_client()` tries in order:
1. Secure session: native session file (`~/.mm/mm_session.pickle`), then `MONARCH_TOKEN` env var, then keyring
2. `MONARCH_EMAIL`/`MONARCH_PASSWORD` env vars (auto-login fallback)

Note: `MONARCH_TOKEN` is checked inside `secure_session.load_token()`, which is only reached if the native session file load fails. A stale session file can shadow a fresh `MONARCH_TOKEN`.

### Safety System (split across 4 files)

- **`safety_config.py`** — `SafetyConfig` class: loads/saves `~/.mm/safety_config.json`, defines which operations need approval vs warning.
- **`safety_guard.py`** — `SafetyGuard` class: checks operations, records them to JSONL audit log, generates rollback info.
- **`safety_decorator.py`** — `require_safety_check` decorator factory: wraps write tools to check+record operations.
- **`safety.py`** — Facade module: re-exports everything, holds the global `_safety_guard` singleton.

Destructive operations (delete_*, upload_balance_history) require approval. Write operations (create_*, update_*, set_*) trigger warnings. Emergency stop blocks all writes.

### SDK: `monarchmoneycommunity`

The project uses `monarchmoneycommunity` (a community-maintained fork of the original `monarchmoney` SDK). Same Python import path (`from monarchmoney import ...`). The community fork has the correct API domain natively — no monkey-patching needed.

### OAuth State Management (`oauth_state.py`)

For HTTP mode with Redis-backed OAuth storage: encrypted Redis store, auto-repair on `invalid_token` spikes (3+ in 60s triggers purge of volatile OAuth collections).

### Data Directory

All runtime data lives under `~/.mm/` (via `paths.py`): session files, safety config, operation logs. Falls back to `/tmp` if home directory is unresolvable.

## CI/CD

- **CI** (`ci.yml`): Tests on Python 3.11-3.14, lint with ruff, type-check with ty. All use `uv`.
- **CD** (`cd.yml`): On push to main, builds Docker image, deploys to Cloud Run, runs health/readiness checks, then a full MCP smoke test (initialize -> tools/list -> tools/call).

## Code Style

- Ruff with rules: E, F, I, UP, B, SIM. Line length 88. Double quotes.
- `asyncio_mode = "auto"` in pytest — no need for `@pytest.mark.asyncio`.
- Tests use `unittest.mock` (not pytest-mock). The `conftest.py` provides `mock_monarch_client`, `mock_keyring`, `isolated_safety_guard` fixtures. An autouse fixture isolates FastMCP state to a temp dir — check `conftest.py` first if tests leak state or fail with permission errors.
- Aggregation tools share a transaction fetch cap defined in `tools/_common.py`. New aggregation tools should use that constant rather than hardcoding a limit.
