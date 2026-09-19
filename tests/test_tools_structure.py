"""Tests for tool structure and SDK coverage."""

import ast
import inspect
from pathlib import Path

from fastmcp import FastMCP
from monarchmoney import MonarchMoney

# SDK methods that are intentionally not wrapped as MCP tools.
# These are excluded from the coverage denominator.
INTENTIONALLY_UNWRAPPED = {
    "login",  # Auth handled at server startup
    "interactive_login",  # Auth handled at server startup
    "multi_factor_authenticate",  # Auth handled at server startup
    "gql_call",  # Raw GraphQL — unsafe for LLM use
}

MINIMUM_COVERAGE = 0.95

TOOLS_DIR = (
    Path(__file__).resolve().parent.parent / "src" / "monarch_mcp_server" / "tools"
)


def _get_sdk_public_async_methods() -> set[str]:
    """Return all public async method names on MonarchMoney."""
    return {
        name
        for name, method in inspect.getmembers(
            MonarchMoney, predicate=inspect.isfunction
        )
        if not name.startswith("_") and inspect.iscoroutinefunction(method)
    }


def _get_mcp_sdk_calls() -> set[str]:
    """Parse tools/*.py with AST to find all client.<method>() calls."""
    calls: set[str] = set()
    for py_file in TOOLS_DIR.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "client"
            ):
                calls.add(node.func.attr)
    return calls


def test_register_tools_exists():
    """Verify that register_tools function exists in tools module."""
    from monarch_mcp_server.tools import register_tools

    assert callable(register_tools)


def test_register_tools_accepts_mcp():
    """Verify that register_tools accepts an mcp instance."""
    from monarch_mcp_server.tools import register_tools

    mcp = FastMCP("test")
    register_tools(mcp)


class TestSDKCoverage:
    """Verify MCP tools cover the monarchmoney SDK surface."""

    def test_no_ghost_sdk_calls(self):
        """Fail if any MCP tool calls a MonarchMoney method that doesn't exist."""
        sdk_methods = _get_sdk_public_async_methods()
        mcp_calls = _get_mcp_sdk_calls()

        ghost_calls = mcp_calls - sdk_methods
        assert not ghost_calls, (
            f"MCP tools call SDK methods that don't exist: {sorted(ghost_calls)}"
        )

    def test_sdk_coverage_minimum(self):
        """Fail if SDK method coverage drops below the minimum threshold."""
        sdk_methods = _get_sdk_public_async_methods()
        mcp_calls = _get_mcp_sdk_calls()

        # Exclude intentionally unwrapped from the denominator
        coverable = sdk_methods - INTENTIONALLY_UNWRAPPED
        covered = mcp_calls & coverable
        uncovered = coverable - mcp_calls

        coverage = len(covered) / len(coverable) if coverable else 1.0

        # Print report for visibility (shows in pytest -v output)
        print("\n--- SDK Coverage Report ---")
        print(f"SDK public async methods: {len(sdk_methods)}")
        print(f"Intentionally skipped:    {len(INTENTIONALLY_UNWRAPPED)}")
        print(f"Coverable methods:        {len(coverable)}")
        print(f"Covered by MCP tools:     {len(covered)}")
        print(f"Coverage:                 {coverage:.0%}")
        if uncovered:
            print(f"Uncovered methods:        {sorted(uncovered)}")

        assert coverage >= MINIMUM_COVERAGE, (
            f"SDK coverage {coverage:.0%} is below minimum {MINIMUM_COVERAGE:.0%}. "
            f"Uncovered: {sorted(uncovered)}"
        )
