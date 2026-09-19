"""Declare each tool's behaviour using MCP's own annotations.

MCP defines `ToolAnnotations` so a client can tell what a tool does before
calling it — whether it only reads, whether it destroys data, whether calling
it twice differs from calling it once. Clients use those hints to decide what
to confirm with the user. This server declared none of them, so to any client
`delete_account` looked exactly like `get_accounts`.

That matters more here than in most servers. The confirmation gate in
`approval.py` is in-band: the caller asks, the server challenges, the caller
answers. It cannot tell whether a human ever saw the challenge. Annotations are
the part of the standard that lets the *client* put a person in the loop, so
declaring them is not decoration — it is the half of the design this server was
missing.

Annotations are derived from the safety tiers rather than written out per tool.
Those tiers already decide what is destructive; a second hand-maintained copy
would be one more thing to drift, which is the failure this codebase keeps
finding. `tests/test_annotations.py` asserts every registered tool carries
annotations and that they still agree with `SafetyConfig`.
"""

from __future__ import annotations

import logging

from mcp.types import ToolAnnotations

from monarch_mcp_server.safety_config import SafetyConfig
from monarch_mcp_server.safety_decorator import SAFETY_OPERATION_ATTR

logger = logging.getLogger(__name__)

# Tools that change server-side safety state rather than financial data. They
# are not reads, but they destroy nothing.
_SAFETY_CONTROLS = frozenset({"enable_emergency_stop", "disable_emergency_stop"})

# Tools that ask Monarch to re-sync. They create no data of their own, but they
# do cause work upstream, so calling them is not free the way a read is.
_REFRESH_TOOLS = frozenset({"refresh_accounts", "request_accounts_refresh_and_wait"})

# Write operations where repeating the identical call lands somewhere new
# rather than re-reaching the same state. Everything else that writes settles
# to the same result, so it is idempotent in the sense MCP means.
_NON_IDEMPOTENT = frozenset(
    {
        "create_transaction",  # a second call is a second transaction
        "create_manual_account",
        "create_transaction_category",
        "create_tag",
        "upload_attachment",  # attaches another copy of the file
    }
)


def annotations_for(
    tool_name: str,
    *,
    is_guarded_write: bool,
    config: SafetyConfig,
) -> ToolAnnotations:
    """Describe one tool's behaviour.

    Args:
        tool_name: The registered tool name.
        is_guarded_write: Whether the tool is wrapped in ``require_safety_check``,
            which is what marks it as writing to Monarch at all.
        config: Supplies the destructive tier, so this never restates it.
    """
    read_only = not is_guarded_write and tool_name not in (
        _SAFETY_CONTROLS | _REFRESH_TOOLS
    )

    # Field names, not their camelCase aliases. Both are accepted
    # (`populate_by_name`), and both serialize to the camelCase the wire format
    # uses, but the aliases read as unknown kwargs to static analysis.
    return ToolAnnotations(
        read_only_hint=read_only,
        # The spec says this is meaningful only when readOnlyHint is false, so
        # a read reports False rather than leaving a client to guess.
        destructive_hint=(not read_only) and config.requires_approval(tool_name),
        idempotent_hint=read_only or tool_name not in _NON_IDEMPOTENT,
        # Every tool talks to one account on one known service. "Open world"
        # is for tools whose reach is not enumerable, like a web search.
        open_world_hint=False,
    )


def annotations_for_function(func) -> ToolAnnotations:
    """Describe a tool from the function about to be registered.

    ``require_safety_check`` tags the wrapper it returns with the operation
    name, so whether a tool writes — and which tier it writes at — is read back
    from the decorator that already decided it. Nothing is restated.
    """
    operation = getattr(func, SAFETY_OPERATION_ATTR, None)
    return annotations_for(
        operation or func.__name__,
        is_guarded_write=operation is not None,
        config=SafetyConfig(),
    )
