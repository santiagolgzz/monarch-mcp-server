"""Tests for budget management tools."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools

from . import sdk_fixtures
from .conftest import permit_all


@pytest.fixture
def mcp():
    return FastMCP("test")


@pytest.mark.asyncio
async def test_get_budgets_reads_the_real_response_shape(mcp):
    """get_budgets must read `budgetData`, the key the SDK actually returns.

    It read a top-level `budgets` key for months. That key does not exist in
    GetJointPlanningData, so the tool always returned an empty list — and the
    mock invented the same key, so the suite agreed with the bug.
    """
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_budgets.return_value = sdk_fixtures.budgets_response(
        category_id="cat_food", month="2026-03-01", budgeted=300.0
    )

    with patch(
        "monarch_mcp_server.tools.budgets.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp.get_tool("get_budgets")
        data = await tool.fn()

        assert len(data) == 1, "the real response shape must produce a row"
        row = data[0]
        assert row["kind"] == "category"
        assert row["category_id"] == "cat_food"
        assert row["month"] == "2026-03-01"
        assert row["budgeted"] == 300.0
        assert row["actual"] == 120.0
        assert row["remaining"] == 180.0


@pytest.mark.asyncio
async def test_get_budgets_includes_category_groups(mcp):
    """Group-level budgets live in a sibling bucket and count too."""
    register_tools(mcp)

    payload = sdk_fixtures.budgets_response()
    payload["budgetData"]["monthlyAmountsByCategoryGroup"] = [
        {
            "categoryGroup": {"id": "grp_1"},
            "monthlyAmounts": [
                {
                    "month": "2026-03-01",
                    "plannedCashFlowAmount": 900.0,
                    "actualAmount": 400.0,
                    "remainingAmount": 500.0,
                }
            ],
        }
    ]

    mock_client = AsyncMock()
    mock_client.get_budgets.return_value = payload

    with patch(
        "monarch_mcp_server.tools.budgets.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp.get_tool("get_budgets")
        data = await tool.fn()

        kinds = {row["kind"] for row in data}
        assert kinds == {"category", "category_group"}
        group_row = next(r for r in data if r["kind"] == "category_group")
        assert group_row["category_id"] == "grp_1"
        assert group_row["budgeted"] == 900.0


@pytest.mark.asyncio
async def test_get_budgets_empty_list(mcp):
    """An empty budgetData yields no rows rather than raising."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_budgets.return_value = {
        "budgetData": {
            "monthlyAmountsByCategory": [],
            "monthlyAmountsByCategoryGroup": [],
        }
    }

    with patch(
        "monarch_mcp_server.tools.budgets.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp.get_tool("get_budgets")
        assert await tool.fn() == []


@pytest.mark.asyncio
async def test_get_budgets_missing_budget_data_key(mcp):
    """A response with no budgetData at all must not raise."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_budgets.return_value = {}

    with patch(
        "monarch_mcp_server.tools.budgets.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp.get_tool("get_budgets")
        assert await tool.fn() == []


@pytest.mark.asyncio
async def test_get_budgets_tolerates_partial_month_entries(mcp):
    """Missing amount fields come through as None instead of raising."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.get_budgets.return_value = {
        "budgetData": {
            "monthlyAmountsByCategory": [
                {
                    "category": {"id": "cat_1"},
                    "monthlyAmounts": [{"month": "2026-03-01"}],
                }
            ]
        }
    }

    with patch(
        "monarch_mcp_server.tools.budgets.get_monarch_client", return_value=mock_client
    ):
        tool = await mcp.get_tool("get_budgets")
        data = await tool.fn()
        assert len(data) == 1
        assert data[0]["budgeted"] is None
        assert data[0]["category_id"] == "cat_1"


@pytest.mark.asyncio
async def test_set_budget_amount_success(mcp):
    """Verify set_budget_amount calls SDK with correct parameters."""
    register_tools(mcp)

    mock_client = AsyncMock()
    mock_client.set_budget_amount.return_value = {
        "success": True,
        "category_id": "cat_123",
        "amount": 750.0,
    }

    with patch(
        "monarch_mcp_server.tools.budgets.get_monarch_client", return_value=mock_client
    ):
        # Also mock safety guard - must return (True, None) tuple
        with patch("monarch_mcp_server.safety.get_safety_guard") as mock_guard:
            permit_all(mock_guard.return_value)
            tool = await mcp.get_tool("set_budget_amount")
            data = await tool.fn(category_id="cat_123", amount=750.0)
            assert data["success"] is True
            mock_client.set_budget_amount.assert_called_once_with(
                amount=750.0,
                category_id="cat_123",
                category_group_id=None,
                timeframe="month",
                start_date=None,
                apply_to_future=False,
            )
