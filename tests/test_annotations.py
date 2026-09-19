"""Every tool must declare MCP annotations, and they must match the safety tiers.

Annotations are how a *client* learns that `delete_account` is not
`get_accounts`, and therefore how a client puts a person in front of the
difference. This server's own confirmation gate cannot: it runs in-band, so it
only ever learns that the caller answered, never that a human saw the question.

A tool that ships unannotated is a tool no client can gate, and nothing else in
the suite would notice — which is why this is checked rather than assumed.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.safety_config import SafetyConfig
from monarch_mcp_server.tools import register_tools

READ_PREFIXES = ("get_", "search_", "is_", "check_")

# Not reads, but they destroy no financial data either.
NON_DESTRUCTIVE_NON_READS = {
    "enable_emergency_stop",
    "disable_emergency_stop",
    "refresh_accounts",
    "request_accounts_refresh_and_wait",
}


@lru_cache(maxsize=1)
def registered():
    """All registered tools, keyed by name."""
    mcp = FastMCP("annotations-check")
    register_tools(mcp)
    return {tool.name: tool for tool in asyncio.run(mcp.list_tools())}


@lru_cache(maxsize=1)
def defaults() -> dict:
    config = SafetyConfig(config_path="/nonexistent/safety_config.json").config
    return {
        "approval": set(config["require_approval"]),
        "warn": set(config["warn_before_execute"]),
    }


def test_every_tool_declares_annotations():
    unannotated = sorted(
        name for name, tool in registered().items() if tool.annotations is None
    )
    assert not unannotated, (
        f"These tools reach clients with no behaviour hints: {unannotated}. "
        "Register them with @annotated_tool(mcp), not a bare @mcp.tool()."
    )


def test_read_tools_are_marked_read_only():
    wrong = {
        name: tool.annotations.read_only_hint
        for name, tool in registered().items()
        if name.startswith(READ_PREFIXES) and not tool.annotations.read_only_hint
    }
    assert not wrong, f"Read tools not marked readOnlyHint: {sorted(wrong)}"


def test_write_tools_are_not_marked_read_only():
    writes = defaults()["approval"] | defaults()["warn"]
    wrong = sorted(
        name
        for name, tool in registered().items()
        if name in writes and tool.annotations.read_only_hint
    )
    assert not wrong, (
        f"These write tools claim readOnlyHint: {wrong}. A client would skip "
        "confirmation for them."
    )


def test_destructive_hint_matches_the_approval_tier():
    """The one hint that decides whether a client warns before acting."""
    expected = defaults()["approval"]
    actual = {
        name for name, tool in registered().items() if tool.annotations.destructive_hint
    }
    assert actual == expected, (
        "destructiveHint disagrees with SafetyConfig's require_approval list.\n"
        f"annotated destructive: {sorted(actual)}\n"
        f"config says destructive: {sorted(expected)}"
    )


def test_no_read_tool_is_marked_destructive():
    """The spec treats destructiveHint as meaningful only when not read-only."""
    wrong = sorted(
        name
        for name, tool in registered().items()
        if tool.annotations.read_only_hint and tool.annotations.destructive_hint
    )
    assert not wrong, f"Tools marked both read-only and destructive: {wrong}"


def test_non_destructive_non_reads_are_classified_deliberately():
    for name in NON_DESTRUCTIVE_NON_READS:
        annotations = registered()[name].annotations
        assert annotations.read_only_hint is False, f"{name} should not be read-only"
        assert annotations.destructive_hint is False, f"{name} destroys nothing"


@pytest.mark.parametrize(
    "name",
    [
        "create_transaction",
        "create_manual_account",
        "create_transaction_category",
        "create_tag",
        "upload_attachment",
    ],
)
def test_creates_are_not_idempotent(name):
    """Calling these twice leaves two things behind, not one."""
    assert registered()[name].annotations.idempotent_hint is False


@pytest.mark.parametrize(
    "name",
    ["delete_transaction", "update_transaction", "categorize_transaction"],
)
def test_deletes_and_updates_are_idempotent(name):
    """Repeating them re-reaches the same state rather than a new one."""
    assert registered()[name].annotations.idempotent_hint is True


def test_nothing_claims_an_open_world():
    """Every tool acts on one account on one known service."""
    wrong = sorted(
        name for name, tool in registered().items() if tool.annotations.open_world_hint
    )
    assert not wrong, f"Tools claiming openWorldHint: {wrong}"


def test_annotations_survive_a_config_that_widens_the_destructive_tier():
    """Hints are derived, not hardcoded, so moving a tier moves them.

    If this ever fails, someone has written the destructive list down a second
    time — the duplication this module exists to avoid.
    """
    from monarch_mcp_server.annotations import annotations_for

    class FakeConfig:
        def requires_approval(self, name: str) -> bool:
            return name == "set_budget_amount"

    widened = annotations_for(
        "set_budget_amount", is_guarded_write=True, config=FakeConfig()
    )
    assert widened.destructive_hint is True

    narrowed = annotations_for(
        "delete_transaction", is_guarded_write=True, config=FakeConfig()
    )
    assert narrowed.destructive_hint is False
