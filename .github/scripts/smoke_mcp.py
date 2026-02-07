"""CD smoke test: verify MCP server responds to initialize, tools/list, and tools/call."""

import json
import sys
import urllib.request

def mcp_request(url: str, token: str, body: dict, session_id: str | None = None) -> tuple[dict, str | None]:
    """Send a JSON-RPC request to the MCP endpoint, return (parsed_result, session_id)."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["mcp-session-id"] = session_id

    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        sid = resp.headers.get("mcp-session-id") or session_id
        raw = resp.read().decode().strip()

    # Handle SSE responses: extract last data: line
    if raw.startswith("event:"):
        data_lines = [
            line.removeprefix("data: ").strip()
            for line in raw.splitlines()
            if line.startswith("data: ")
        ]
        if not data_lines:
            raise SystemExit("No SSE data payload found")
        raw = data_lines[-1]

    parsed = json.loads(raw)
    if "error" in parsed:
        raise SystemExit(f"JSON-RPC error: {parsed['error']}")
    return parsed, sid


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"Usage: {sys.argv[0]} <mcp_url> <auth_token>")

    mcp_url, token = sys.argv[1], sys.argv[2]

    # Step 1: Initialize
    init_body = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "cd-smoke", "version": "1.0.0"},
        },
    }
    result, session_id = mcp_request(mcp_url, token, init_body)
    if "result" not in result:
        raise SystemExit("initialize: missing result")
    print("OK: initialize")

    # Step 2: List tools
    list_body = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    result, session_id = mcp_request(mcp_url, token, list_body, session_id)
    tools = result.get("result", {}).get("tools", [])
    if not tools:
        raise SystemExit("tools/list: returned no tools")
    print(f"OK: tools/list ({len(tools)} tools)")

    # Step 3: Call a safe tool
    call_body = {
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "get_safety_stats", "arguments": {}},
    }
    result, session_id = mcp_request(mcp_url, token, call_body, session_id)
    tool_result = result.get("result")
    if tool_result is None:
        raise SystemExit("tools/call: missing result")
    if tool_result.get("isError") is True:
        raise SystemExit(f"tools/call: isError=true: {tool_result}")
    print("OK: tools/call (get_safety_stats)")

    print("Smoke test passed")


if __name__ == "__main__":
    main()
