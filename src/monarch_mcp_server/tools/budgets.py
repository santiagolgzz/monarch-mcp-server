"""
Budget management tools for Monarch Money.

Tools for viewing and managing budgets.
"""

import logging

from fastmcp import FastMCP

from monarch_mcp_server.client import get_monarch_client
from monarch_mcp_server.exceptions import ValidationError
from monarch_mcp_server.safety import require_safety_check
from monarch_mcp_server.utils import validate_date_format

from ._common import tool_handler

logger = logging.getLogger(__name__)


def register_budget_tools(mcp: FastMCP) -> None:
    """Register budget management tools with the FastMCP instance."""

    @mcp.tool()
    @tool_handler("get_budgets")
    async def get_budgets(
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """Get budget information from Monarch Money.

        Args:
            start_date: Start of the budget period, YYYY-MM-DD. Defaults to
                the SDK's current-period behavior when omitted.
            end_date: End of the budget period, YYYY-MM-DD.
        """
        validated_start = validate_date_format(start_date, "start_date")
        validated_end = validate_date_format(end_date, "end_date")

        client = await get_monarch_client()
        budgets = await client.get_budgets(
            start_date=validated_start,
            end_date=validated_end,
        )
        budget_list = []
        for budget in budgets.get("budgets", []):
            budget_info = {
                "id": budget.get("id"),
                "name": budget.get("name"),
                "amount": budget.get("amount"),
                "spent": budget.get("spent"),
                "remaining": budget.get("remaining"),
                "category": budget.get("category", {}).get("name"),
                "period": budget.get("period"),
            }
            budget_list.append(budget_info)
        return budget_list

    @mcp.tool()
    @require_safety_check("set_budget_amount")
    @tool_handler("set_budget_amount")
    async def set_budget_amount(
        amount: float,
        category_id: str | None = None,
        category_group_id: str | None = None,
        timeframe: str = "month",
        start_date: str | None = None,
        apply_to_future: bool = False,
    ) -> dict:
        """Set or update a budget amount for a category or category group.

        Exactly one of category_id or category_group_id must be given.

        Args:
            amount: The budget amount. Zero clears the budget. Negative values
                indicate over-budget.
            category_id: Budget a single category. Mutually exclusive with
                category_group_id.
            category_group_id: Budget a whole category group. Mutually
                exclusive with category_id.
            timeframe: Budget period. "month" is currently the only value
                Monarch accepts.
            start_date: Start of the period, YYYY-MM-DD. Defaults to the start
                of the current month.
            apply_to_future: Apply this amount to all future periods as well,
                not just the one period. Defaults to False, which changes only
                the targeted period.
        """
        if (category_id is None) == (category_group_id is None):
            raise ValidationError(
                "Specify exactly one of category_id or category_group_id, not "
                "both and not neither."
            )

        validated_start = validate_date_format(start_date, "start_date")

        client = await get_monarch_client()
        return await client.set_budget_amount(
            amount=amount,
            category_id=category_id,
            category_group_id=category_group_id,
            timeframe=timeframe,
            start_date=validated_start,
            apply_to_future=apply_to_future,
        )
