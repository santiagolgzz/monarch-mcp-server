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
uv run ruff check src/ tests/ scripts/
uv run ruff format --check src/ tests/ scripts/

# Auto-fix lint issues
uv run ruff check --fix src/ tests/ scripts/
uv run ruff format src/ tests/ scripts/

# Type check (uses ty, not mypy)
uv run ty check src/

# SDK coverage report / ratchet (see "SDK Coverage Ratchet" below)
uv run python scripts/sdk_coverage.py
uv run python scripts/sdk_coverage.py --check
uv run python scripts/sdk_coverage.py --update-baseline

# Enable the local git hooks (secret scan + coverage ratchet)
git config core.hooksPath .githooks

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

  In `oauth`/`both` mode, `auth_allowlist.py` wraps `GitHubProvider` so that
  `verify_token` additionally checks the authenticated identity against
  `MCP_ALLOWED_GITHUB_USERS`. OAuth alone only proves the caller has *a* GitHub
  account; the allowlist is what scopes the endpoint to specific people. It is
  required — `create_mcp_server` raises when it is unset, so the endpoint can
  never come up accepting any account.
  - Optional CI smoke endpoint at `/mcp-smoke/mcp` (when `MCP_ENABLE_CI_SMOKE=true`)

### Tool Registration Pattern

Tools register with `@annotated_tool(mcp)`, **not** a bare `@mcp.tool()`. It
declares the tool's MCP `ToolAnnotations` — `readOnlyHint`, `destructiveHint`,
`idempotentHint`, `openWorldHint` — which is how a *client* learns that
`delete_account` is not `get_accounts` and puts a person in front of the
difference. The server's own confirmation gate cannot do that: it runs in-band
and only ever learns that the caller answered.

Hints are derived, never restated. `require_safety_check` tags its wrapper with
the operation name, and `annotations.py` reads that tag plus `SafetyConfig` to
decide the hints, so the destructive tier is written down exactly once.
`tests/test_annotations.py` fails if any tool ships unannotated or if the hints
drift from the config.


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

## SDK Coverage Ratchet

`scripts/sdk_coverage.py` compares the `monarchmoney` SDK's public surface against what this server actually calls, and tracks three ways capability can go unexposed:

1. **Uncovered methods** — SDK methods with no call site in `src/`.
2. **Param gaps** — parameters of a called method never passed at any call site. This is the issue #15 class of bug: `create_transaction` existed and was called, but dropped the SDK's `update_balance` option, so manual transactions never moved the balance.
3. **Unanalyzable calls** — call sites using a `**kwargs` splat, where params can't be resolved statically. Tracked rather than skipped silently, so a gap can't be hidden by switching a call to a splat.

Results are ratcheted against `scripts/sdk_coverage_baseline.json`. The check fails in **both** directions: a new gap fails because capability was lost, and a baseline entry that no longer reproduces also fails, so closing a gap forces the baseline to tighten. Otherwise the baseline would rot into a list of things that used to be broken.

Enforced in two places:
- **Pre-commit** via `.githooks/pre-commit` (opt in with `git config core.hooksPath .githooks`). Skipped if `uv` is unavailable.
- **CI** via `tests/test_sdk_coverage.py`, which runs unconditionally and cannot be bypassed with `--no-verify`.

When you deliberately widen or accept a gap, re-record it with `--update-baseline` and say why in the commit message. The issue #15 gap is additionally pinned by its own test, so `--update-baseline` alone cannot re-accept it.

## Safety System

Split across `safety_config.py` (policy), `safety_guard.py` (checks, counters,
audit log), `safety_decorator.py` (the wrapper), `pre_state.py` (snapshots),
`rollback.py` (undo planning), `approval.py` (confirmation tokens), and
`safety.py` (facade + global singleton).

`require_safety_check` runs four steps in this order, and the order matters:

1. **`check_operation`** — emergency stop, then the daily cap. Both refuse
   before any work happens.
2. **`pre_state.capture`** — snapshot the record the write is about to change.
   Best-effort: a failure is recorded as `pre_state_error` and the write still
   proceeds, because refusing a delete over a failed snapshot read is the worse
   trade.
3. **`confirm_operation`** — the two-step token gate, *after* capture so the
   challenge can describe what is about to be destroyed.
4. **run, then `record_operation`** — successes and failures alike.

### What was wrong before

Three claims the code made and did not honor. Each is now pinned by a test:

- **`require_approval` gated nothing.** `check_operation` returned True for it,
  so "destructive" operations ran exactly like warned ones while
  `get_safety_stats` reported `approval_required_for` (issue #20).
- **`reversible` was hardcoded True** in every rollback branch, and
  `_extract_id_from_result` read only top-level keys — but the SDK returns
  GraphQL envelopes, so `created_id` was always None. Nothing captured
  pre-state, so deletes and updates pointed at data they had destroyed.
- **Failures were never logged.** `record_operation(success=False)` was a no-op
  behind `if success:`.

The through-line is that **test fixtures did not match the API**. The mocks
returned flat dicts like `{"id": "txn_1"}`, so the extraction bug passed its
tests. `get_budgets` had the same bug in reverse: it read a `budgets` key that
`GetJointPlanningData` has never returned, and always gave an empty list.

`tests/sdk_fixtures.py` holds shapes transcribed from the SDK's own GraphQL
documents, and `tests/test_sdk_fixture_shapes.py` parses those documents to
check the fixtures still match. **Use those fixtures for any test involving an
SDK response.** A hand-written response shape is how this class of bug returns.

### Invariants

- `reversible` is true only when `reverse_call` holds a complete, executable
  call. Otherwise `blocked_reason` says what is missing. Swept in
  `tests/test_rollback.py` across every operation.
- Snapshots are keyed by **tool parameter name**, not Monarch's field names, so
  they drop straight into a reverse call.
- Confirmation tokens are single-use, bound to `(operation, arguments)`, and
  expire.
- Daily caps count successes only.

## Bundled Claude Skill

`.claude/skills/monarch-money-mcp/` documents the tool surface for agents:
`SKILL.md` plus `references/tools.md`, `references/safety.md`, and
`references/financial-analysis.md`.

It is documentation *of this codebase*, so it goes stale the same way a README
does — except an agent acts on it. It did go stale: for five months it described
`create_transaction` without `update_balance`, so an agent following it would
write the exact bug issue #15 fixed.

`tests/test_skill_accuracy.py` now guards it. The test derives truth from the
registered FastMCP tools and `SafetyConfig`'s defaults, then checks the skill's
tables agree on:

- tool names, registration order, and gapless numbering
- per-section and contents counts
- safety tier labels (Read / Recorded / Warn / Approval / Action)
- the `### <tool> Parameters` tables — every parameter, and whether it's required
- the headline tool count and safety bullets in `SKILL.md`
- that no skill file names a tool that doesn't exist

**Adding or renaming a tool, or changing a safety tier, will fail this test
until the skill is updated.** That's the point — fix the skill, don't loosen the
test. Parameter tables are opt-in: a tool only gets checked if `tools.md` has a
`### <tool> Parameters` section for it, so add one when a tool's arguments are
subtle enough that an agent could get them wrong.

## Code Style

- Ruff with rules: E, F, I, UP, B, SIM. Line length 88. Double quotes.
- `asyncio_mode = "auto"` in pytest — no need for `@pytest.mark.asyncio`.
- Tests use `unittest.mock` (not pytest-mock). The `conftest.py` provides `mock_monarch_client`, `mock_keyring`, `isolated_safety_guard` fixtures. An autouse fixture isolates FastMCP state to a temp dir — check `conftest.py` first if tests leak state or fail with permission errors.
- Aggregation tools share a transaction fetch cap defined in `tools/_common.py`. New aggregation tools should use that constant rather than hardcoding a limit.
