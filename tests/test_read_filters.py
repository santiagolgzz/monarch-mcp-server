"""Tests for SDK read filters exposed through the MCP tools.

These cover the passthrough of optional SDK filters that previously had no way
to be reached from a tool call. Each test asserts both directions: the filter
reaches the SDK when set, and stays unset (no filtering) when omitted.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools

TXN_PATH = "monarch_mcp_server.tools.transactions.get_monarch_client"
BUDGET_PATH = "monarch_mcp_server.tools.budgets.get_monarch_client"

BOOLEAN_FILTERS = [
    "has_attachments",
    "has_notes",
    "hidden_from_reports",
    "is_split",
    "is_recurring",
    "imported_from_mint",
    "synced_from_institution",
]


@pytest.fixture
def mcp():
    return FastMCP("test")


@pytest.fixture
def client():
    mock = AsyncMock()
    mock.get_transactions.return_value = {"allTransactions": {"results": []}}
    mock.get_recurring_transactions.return_value = {}
    mock.get_transaction_details.return_value = {}
    mock.get_budgets.return_value = {"budgets": []}
    return mock


async def test_get_transactions_defaults_apply_no_extra_filters(mcp, client):
    """Omitting the new filters must not filter anything."""
    register_tools(mcp)
    with patch(TXN_PATH, return_value=client):
        tool = await mcp.get_tool("get_transactions")
        await tool.fn()

    kwargs = client.get_transactions.call_args.kwargs
    assert kwargs["tag_ids"] == []
    for name in BOOLEAN_FILTERS:
        assert kwargs[name] is None, f"{name} should default to no filtering"


@pytest.mark.parametrize("filter_name", BOOLEAN_FILTERS)
@pytest.mark.parametrize("value", [True, False])
async def test_get_transactions_boolean_filters_reach_sdk(
    mcp, client, filter_name, value
):
    """Each boolean filter must reach the SDK, including when set to False."""
    register_tools(mcp)
    with patch(TXN_PATH, return_value=client):
        tool = await mcp.get_tool("get_transactions")
        await tool.fn(**{filter_name: value})

    kwargs = client.get_transactions.call_args.kwargs
    assert kwargs[filter_name] is value


async def test_get_transactions_tag_ids_reach_sdk(mcp, client):
    register_tools(mcp)
    with patch(TXN_PATH, return_value=client):
        tool = await mcp.get_tool("get_transactions")
        await tool.fn(tag_ids=["tag_1", "tag_2"])

    assert client.get_transactions.call_args.kwargs["tag_ids"] == ["tag_1", "tag_2"]


async def test_get_recurring_transactions_date_range(mcp, client):
    register_tools(mcp)
    with patch(TXN_PATH, return_value=client):
        tool = await mcp.get_tool("get_recurring_transactions")
        await tool.fn(start_date="2024-01-01", end_date="2024-01-31")

    kwargs = client.get_recurring_transactions.call_args.kwargs
    assert kwargs["start_date"] == "2024-01-01"
    assert kwargs["end_date"] == "2024-01-31"


async def test_get_recurring_transactions_defaults_to_no_range(mcp, client):
    register_tools(mcp)
    with patch(TXN_PATH, return_value=client):
        tool = await mcp.get_tool("get_recurring_transactions")
        await tool.fn()

    kwargs = client.get_recurring_transactions.call_args.kwargs
    assert kwargs["start_date"] is None
    assert kwargs["end_date"] is None


async def test_get_recurring_transactions_rejects_bad_date(mcp, client):
    register_tools(mcp)
    with patch(TXN_PATH, return_value=client):
        tool = await mcp.get_tool("get_recurring_transactions")
        with pytest.raises(RuntimeError, match="Invalid date format"):
            await tool.fn(start_date="01-2024-31")

    client.get_recurring_transactions.assert_not_called()


async def test_get_transaction_details_redirect_posted_defaults_true(mcp, client):
    """Default must match the SDK and the Monarch app."""
    register_tools(mcp)
    with patch(TXN_PATH, return_value=client):
        tool = await mcp.get_tool("get_transaction_details")
        await tool.fn(transaction_id="txn_1")

    assert client.get_transaction_details.call_args.kwargs["redirect_posted"] is True


async def test_get_transaction_details_redirect_posted_can_be_disabled(mcp, client):
    register_tools(mcp)
    with patch(TXN_PATH, return_value=client):
        tool = await mcp.get_tool("get_transaction_details")
        await tool.fn(transaction_id="txn_1", redirect_posted=False)

    assert client.get_transaction_details.call_args.kwargs["redirect_posted"] is False


async def test_get_budgets_date_range(mcp, client):
    register_tools(mcp)
    with patch(BUDGET_PATH, return_value=client):
        tool = await mcp.get_tool("get_budgets")
        await tool.fn(start_date="2024-03-01", end_date="2024-03-31")

    kwargs = client.get_budgets.call_args.kwargs
    assert kwargs["start_date"] == "2024-03-01"
    assert kwargs["end_date"] == "2024-03-31"


async def test_get_budgets_defaults_to_no_range(mcp, client):
    register_tools(mcp)
    with patch(BUDGET_PATH, return_value=client):
        tool = await mcp.get_tool("get_budgets")
        await tool.fn()

    kwargs = client.get_budgets.call_args.kwargs
    assert kwargs["start_date"] is None
    assert kwargs["end_date"] is None


async def test_get_budgets_rejects_bad_date(mcp, client):
    register_tools(mcp)
    with patch(BUDGET_PATH, return_value=client):
        tool = await mcp.get_tool("get_budgets")
        with pytest.raises(RuntimeError, match="Invalid date format"):
            await tool.fn(end_date="not-a-date")

    client.get_budgets.assert_not_called()
