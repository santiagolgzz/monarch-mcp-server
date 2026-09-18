"""Ratchet tests for SDK coverage.

These guard the class of bug that issue #15 was: an MCP tool that exists and
calls the SDK, but silently drops one of the SDK's options (there,
``create_transaction``'s ``update_balance``).

The ratchet fails in both directions on purpose. A new gap fails because
capability was lost. A baseline entry that no longer reproduces also fails,
because otherwise the baseline would slowly rot into a list of things that used
to be broken, and would stop catching anything.
"""

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "sdk_coverage.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("sdk_coverage", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sdk_coverage = _load_module()


@pytest.fixture(scope="module")
def result():
    return sdk_coverage.analyze()


def test_script_and_baseline_exist():
    assert SCRIPT.exists(), "scripts/sdk_coverage.py is missing"
    assert sdk_coverage.BASELINE.exists(), "sdk_coverage_baseline.json is missing"


def test_baseline_is_valid_json():
    data = json.loads(sdk_coverage.BASELINE.read_text(encoding="utf-8"))
    assert set(data) >= {"uncovered_methods", "param_gaps", "unanalyzable"}
    assert isinstance(data["param_gaps"], dict)


def test_no_new_coverage_gaps(result):
    """Ratchet, direction 1: coverage must not regress."""
    regressions, _ = sdk_coverage.diff_against_baseline(result)
    assert not regressions, (
        "SDK coverage regressed - capability is exposed by the SDK but not by "
        "this server:\n  " + "\n  ".join(regressions)
    )


def test_baseline_is_not_stale(result):
    """Ratchet, direction 2: fixing a gap must tighten the baseline."""
    _, stale = sdk_coverage.diff_against_baseline(result)
    assert not stale, (
        "SDK coverage improved but the baseline still lists these as gaps. "
        "Re-record it with `uv run python scripts/sdk_coverage.py "
        "--update-baseline`:\n  " + "\n  ".join(stale)
    )


def test_issue_15_regression_create_transaction_update_balance(result):
    """The specific gap from issue #15 must stay closed.

    Pinned explicitly, not just via the baseline, so that a careless
    `--update-baseline` cannot quietly re-accept it.
    """
    gaps = result["param_gaps"].get("create_transaction", [])
    assert "update_balance" not in gaps, (
        "create_transaction no longer passes update_balance to the SDK; "
        "manual transactions would stop affecting account balances (issue #15)"
    )
    assert "create_transaction" not in result["unanalyzable"], (
        "create_transaction is called with a **kwargs splat, so update_balance "
        "can no longer be verified statically (issue #15)"
    )
