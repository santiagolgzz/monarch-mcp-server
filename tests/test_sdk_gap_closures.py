"""Tests for SDK capability that previously had no route through a tool.

Covers the second burn-down pass against the coverage ratchet: the refresh
tools' account targeting, budget write options, attachment upload, credit
history, and the four call sites converted away from **kwargs splats.
"""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import FastMCP

from monarch_mcp_server.tools import register_tools

from .conftest import permit_all

TXN_PATH = "monarch_mcp_server.tools.transactions.get_monarch_client"
ACCT_PATH = "monarch_mcp_server.tools.accounts.get_monarch_client"
BUDGET_PATH = "monarch_mcp_server.tools.budgets.get_monarch_client"
REFRESH_PATH = "monarch_mcp_server.tools.refresh.get_monarch_client"
CAT_PATH = "monarch_mcp_server.tools.categories.get_monarch_client"


@pytest.fixture
def mcp():
    return FastMCP("test")


@pytest.fixture
def client():
    mock = AsyncMock()
    mock.get_accounts.return_value = {
        "accounts": [{"id": "acc_1"}, {"id": "acc_2"}, {"id": "acc_3"}]
    }
    mock.request_accounts_refresh.return_value = True
    mock.request_accounts_refresh_and_wait.return_value = True
    mock.is_accounts_refresh_complete.return_value = True
    mock.get_credit_history.return_value = {"scores": []}
    mock.set_budget_amount.return_value = {"ok": True}
    mock.upload_attachment.return_value = {"id": "att_1"}
    mock.update_account.return_value = {"ok": True}
    mock.create_transaction_category.return_value = {"id": "cat_1"}
    mock.get_transactions_summary.return_value = {"summary": {}}
    return mock


@pytest.fixture
def allow_writes():
    """Bypass the safety guard for write-path tools."""
    with patch("monarch_mcp_server.safety.get_safety_guard") as guard:
        permit_all(guard.return_value)
        guard.return_value.record_operation = MagicMock()
        yield guard


# --------------------------------------------------------------------------
# Refresh targeting: one account, a subset, or all
# --------------------------------------------------------------------------


async def test_refresh_all_accounts_when_ids_omitted(mcp, client):
    register_tools(mcp)
    with patch(REFRESH_PATH, return_value=client):
        tool = await mcp.get_tool("refresh_accounts")
        result = await tool.fn()

    client.request_accounts_refresh.assert_called_once_with(["acc_1", "acc_2", "acc_3"])
    assert result["scope"] == "all"
    assert result["account_count"] == 3


async def test_refresh_single_account(mcp, client):
    register_tools(mcp)
    with patch(REFRESH_PATH, return_value=client):
        tool = await mcp.get_tool("refresh_accounts")
        result = await tool.fn(account_ids=["acc_2"])

    client.request_accounts_refresh.assert_called_once_with(["acc_2"])
    client.get_accounts.assert_not_called()
    assert result["scope"] == "selected"
    assert result["account_count"] == 1


async def test_refresh_subset_of_accounts(mcp, client):
    register_tools(mcp)
    with patch(REFRESH_PATH, return_value=client):
        tool = await mcp.get_tool("refresh_accounts")
        result = await tool.fn(account_ids=["acc_1", "acc_3"])

    client.request_accounts_refresh.assert_called_once_with(["acc_1", "acc_3"])
    assert result["account_count"] == 2


async def test_refresh_reports_when_no_accounts_exist(mcp, client):
    client.get_accounts.return_value = {"accounts": []}
    register_tools(mcp)
    with patch(REFRESH_PATH, return_value=client):
        tool = await mcp.get_tool("refresh_accounts")
        result = await tool.fn()

    assert result["refreshed"] is False
    client.request_accounts_refresh.assert_not_called()


async def test_refresh_and_wait_passes_scope_and_timing(mcp, client):
    register_tools(mcp)
    with patch(REFRESH_PATH, return_value=client):
        tool = await mcp.get_tool("request_accounts_refresh_and_wait")
        await tool.fn(account_ids=["acc_1"], timeout=60, delay=5)

    kwargs = client.request_accounts_refresh_and_wait.call_args.kwargs
    assert kwargs["account_ids"] == ["acc_1"]
    assert kwargs["timeout"] == 60
    assert kwargs["delay"] == 5


async def test_refresh_and_wait_defaults_to_all_accounts(mcp, client):
    """None must reach the SDK, which resolves 'all' itself."""
    register_tools(mcp)
    with patch(REFRESH_PATH, return_value=client):
        tool = await mcp.get_tool("request_accounts_refresh_and_wait")
        await tool.fn()

    kwargs = client.request_accounts_refresh_and_wait.call_args.kwargs
    assert kwargs["account_ids"] is None
    assert kwargs["timeout"] == 300
    assert kwargs["delay"] == 10


async def test_is_refresh_complete_accepts_account_ids(mcp, client):
    register_tools(mcp)
    with patch(REFRESH_PATH, return_value=client):
        tool = await mcp.get_tool("is_accounts_refresh_complete")
        result = await tool.fn(account_ids=["acc_2"])

    kwargs = client.is_accounts_refresh_complete.call_args.kwargs
    assert kwargs["account_ids"] == ["acc_2"]
    assert result["scope"] == "selected"


# --------------------------------------------------------------------------
# Budget write options
# --------------------------------------------------------------------------


async def test_set_budget_amount_write_options(mcp, client, allow_writes):
    register_tools(mcp)
    with patch(BUDGET_PATH, return_value=client):
        tool = await mcp.get_tool("set_budget_amount")
        await tool.fn(
            amount=500.0,
            category_id="cat_1",
            timeframe="month",
            start_date="2024-05-01",
            apply_to_future=True,
        )

    kwargs = client.set_budget_amount.call_args.kwargs
    assert kwargs["apply_to_future"] is True
    assert kwargs["start_date"] == "2024-05-01"
    assert kwargs["timeframe"] == "month"


async def test_set_budget_amount_accepts_category_group(mcp, client, allow_writes):
    register_tools(mcp)
    with patch(BUDGET_PATH, return_value=client):
        tool = await mcp.get_tool("set_budget_amount")
        await tool.fn(amount=100.0, category_group_id="grp_1")

    kwargs = client.set_budget_amount.call_args.kwargs
    assert kwargs["category_group_id"] == "grp_1"
    assert kwargs["category_id"] is None


async def test_set_budget_amount_rejects_both_targets(mcp, client, allow_writes):
    """The SDK raises on both-or-neither; fail earlier with a clear message."""
    register_tools(mcp)
    with patch(BUDGET_PATH, return_value=client):
        tool = await mcp.get_tool("set_budget_amount")
        with pytest.raises(RuntimeError, match="exactly one"):
            await tool.fn(amount=1.0, category_id="cat_1", category_group_id="grp_1")

    client.set_budget_amount.assert_not_called()


async def test_set_budget_amount_rejects_neither_target(mcp, client, allow_writes):
    register_tools(mcp)
    with patch(BUDGET_PATH, return_value=client):
        tool = await mcp.get_tool("set_budget_amount")
        with pytest.raises(RuntimeError, match="exactly one"):
            await tool.fn(amount=1.0)

    client.set_budget_amount.assert_not_called()


# --------------------------------------------------------------------------
# Attachment upload
# --------------------------------------------------------------------------


async def test_upload_attachment_decodes_base64(mcp, client, allow_writes):
    register_tools(mcp)
    payload = b"%PDF-1.4 fake receipt"
    encoded = base64.b64encode(payload).decode()

    with patch(TXN_PATH, return_value=client):
        tool = await mcp.get_tool("upload_attachment")
        result = await tool.fn(
            transaction_id="txn_1",
            file_content_base64=encoded,
            filename="receipt.pdf",
        )

    kwargs = client.upload_attachment.call_args.kwargs
    assert kwargs["file_content"] == payload
    assert kwargs["filename"] == "receipt.pdf"
    assert result["bytes"] == len(payload)


async def test_upload_attachment_rejects_bad_base64(mcp, client, allow_writes):
    register_tools(mcp)
    with patch(TXN_PATH, return_value=client):
        tool = await mcp.get_tool("upload_attachment")
        with pytest.raises(RuntimeError, match="not valid base64"):
            await tool.fn(
                transaction_id="txn_1",
                file_content_base64="this is not base64!!",
                filename="x.pdf",
            )

    client.upload_attachment.assert_not_called()


async def test_upload_attachment_rejects_oversized_file(mcp, client, allow_writes):
    from monarch_mcp_server.tools._common import MAX_ATTACHMENT_BYTES

    register_tools(mcp)
    too_big = base64.b64encode(b"x" * (MAX_ATTACHMENT_BYTES + 1)).decode()

    with patch(TXN_PATH, return_value=client):
        tool = await mcp.get_tool("upload_attachment")
        with pytest.raises(RuntimeError, match="over the"):
            await tool.fn(
                transaction_id="txn_1",
                file_content_base64=too_big,
                filename="big.bin",
            )

    client.upload_attachment.assert_not_called()


# --------------------------------------------------------------------------
# Newly reachable update fields (previously hidden behind **kwargs splats)
# --------------------------------------------------------------------------


async def test_update_transaction_exposes_new_fields(mcp, client, allow_writes):
    register_tools(mcp)
    with patch(TXN_PATH, return_value=client):
        tool = await mcp.get_tool("update_transaction")
        await tool.fn(
            transaction_id="txn_1",
            goal_id="goal_1",
            hide_from_reports=True,
            needs_review=False,
            notes="reconciled",
        )

    kwargs = client.update_transaction.call_args.kwargs
    assert kwargs["goal_id"] == "goal_1"
    assert kwargs["hide_from_reports"] is True
    assert kwargs["needs_review"] is False
    assert kwargs["notes"] == "reconciled"


async def test_update_account_exposes_new_fields(mcp, client, allow_writes):
    register_tools(mcp)
    with patch(ACCT_PATH, return_value=client):
        tool = await mcp.get_tool("update_account")
        await tool.fn(
            account_id="acc_1",
            account_sub_type="savings",
            include_in_net_worth=False,
            hide_from_summary_list=True,
            hide_transactions_from_reports=True,
        )

    kwargs = client.update_account.call_args.kwargs
    assert kwargs["account_sub_type"] == "savings"
    assert kwargs["include_in_net_worth"] is False
    assert kwargs["hide_from_summary_list"] is True
    assert kwargs["hide_transactions_from_reports"] is True


async def test_create_category_rollover_start_month_is_current_by_default(
    mcp, client, allow_writes
):
    """Computed per call, not frozen at import like the SDK's own default."""
    from datetime import datetime

    register_tools(mcp)
    with patch(CAT_PATH, return_value=client):
        tool = await mcp.get_tool("create_transaction_category")
        await tool.fn(name="Coffee", group_id="grp_1")

    start = client.create_transaction_category.call_args.kwargs["rollover_start_month"]
    today = datetime.today()
    assert start.day == 1
    assert (start.year, start.month) == (today.year, today.month)


async def test_create_category_accepts_explicit_rollover_start_month(
    mcp, client, allow_writes
):
    register_tools(mcp)
    with patch(CAT_PATH, return_value=client):
        tool = await mcp.get_tool("create_transaction_category")
        await tool.fn(
            name="Coffee", group_id="grp_1", rollover_start_month="2024-07-01"
        )

    start = client.create_transaction_category.call_args.kwargs["rollover_start_month"]
    assert (start.year, start.month, start.day) == (2024, 7, 1)


async def test_get_transactions_summary_takes_no_filters(mcp, client):
    """Regression: the tool used to splat date filters into a no-arg SDK call.

    That raised TypeError whenever a caller supplied a date. The tool now
    matches the SDK and takes no arguments at all.
    """
    register_tools(mcp)
    with patch(TXN_PATH, return_value=client):
        tool = await mcp.get_tool("get_transactions_summary")
        await tool.fn()

    client.get_transactions_summary.assert_called_once_with()

    # tool_handler wraps the TypeError, but the point stands: a date argument
    # is rejected outright instead of reaching a call that cannot accept it.
    with pytest.raises(RuntimeError, match="unexpected keyword argument"):
        await tool.fn(start_date="2024-01-01")


async def test_get_credit_history_tool(mcp, client):
    register_tools(mcp)
    with patch(ACCT_PATH, return_value=client):
        tool = await mcp.get_tool("get_credit_history")
        result = await tool.fn()

    client.get_credit_history.assert_called_once_with()
    assert result == {"scores": []}
