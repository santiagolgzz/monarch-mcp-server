#!/usr/bin/env python3
"""Measure how much of the monarchmoney SDK surface this server exposes.

Three things are tracked, each a way for SDK capability to go unexposed:

1. **Uncovered methods** - public SDK methods with no call site in ``src/``.
2. **Param gaps** - parameters of a called SDK method that are never passed at
   any call site. This is the class of bug that issue #15 was: the
   ``create_transaction`` tool existed and was called, but silently dropped the
   SDK's ``update_balance`` option, so manual transactions never moved the
   account balance.
3. **Unanalyzable calls** - call sites using ``**kwargs`` splats, where the
   passed parameters cannot be determined statically. These are tracked rather
   than skipped silently, so a gap cannot be hidden by switching a call to a
   splat.

The results are compared against ``sdk_coverage_baseline.json`` as a **ratchet**:
coverage may improve but never regress. ``--check`` fails in both directions —
on a new gap, and on a baseline entry that no longer reproduces (meaning a gap
was fixed but the baseline was not tightened to match).

Usage::

    python scripts/sdk_coverage.py                    # human-readable report
    python scripts/sdk_coverage.py --check            # ratchet check, exits 1 on drift
    python scripts/sdk_coverage.py --update-baseline  # re-record after improving
    python scripts/sdk_coverage.py --json             # machine-readable
"""

from __future__ import annotations

import argparse
import ast
import inspect
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src" / "monarch_mcp_server"
BASELINE = Path(__file__).resolve().parent / "sdk_coverage_baseline.json"

# Parameters that are never meaningful to pass through from a tool.
IGNORED_PARAMS = frozenset({"self", "args", "kwargs"})


def sdk_methods() -> dict[str, inspect.Signature]:
    """Public callables on the SDK client, mapped to their signatures."""
    from monarchmoney import MonarchMoney

    out: dict[str, inspect.Signature] = {}
    for name, obj in inspect.getmembers(MonarchMoney, callable):
        if name.startswith("_"):
            continue
        try:
            out[name] = inspect.signature(obj)
        except (TypeError, ValueError):  # pragma: no cover - builtins
            continue
    return out


class CallSite:
    """One ``<obj>.<method>(...)`` call found in the source tree."""

    def __init__(self, file: str, lineno: int, node: ast.Call) -> None:
        self.file = file
        self.lineno = lineno
        self.kwargs = {kw.arg for kw in node.keywords if kw.arg is not None}
        # `f(**d)` or `f(*a)` - we cannot know statically what is passed.
        self.splat = any(kw.arg is None for kw in node.keywords) or any(
            isinstance(a, ast.Starred) for a in node.args
        )
        self.positional = len([a for a in node.args if not isinstance(a, ast.Starred)])

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CallSite {self.file}:{self.lineno}>"


def call_sites() -> dict[str, list[CallSite]]:
    """Map attribute name -> call sites found anywhere under ``src/``."""
    hits: dict[str, list[CallSite]] = defaultdict(list)
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = str(path.relative_to(REPO_ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                hits[node.func.attr].append(CallSite(rel, node.lineno, node))
    return hits


def analyze() -> dict[str, Any]:
    """Compute the current coverage picture."""
    sdk = sdk_methods()
    calls = call_sites()

    covered = sorted(m for m in sdk if m in calls)
    uncovered = sorted(m for m in sdk if m not in calls)

    param_gaps: dict[str, list[str]] = {}
    unanalyzable: list[str] = []

    for method in covered:
        sig = sdk[method]
        params = {p for p in sig.parameters if p not in IGNORED_PARAMS}
        # Positional args bind to parameters in declaration order.
        ordered = [p for p in sig.parameters if p != "self"]

        passed: set[str] = set()
        has_splat = False
        for site in calls[method]:
            passed |= site.kwargs
            passed |= set(ordered[: site.positional])
            has_splat = has_splat or site.splat

        if has_splat:
            unanalyzable.append(method)
            continue

        missing = sorted(params - passed)
        if missing:
            param_gaps[method] = missing

    total_params = sum(
        len({p for p in sdk[m].parameters if p not in IGNORED_PARAMS})
        for m in covered
        if m not in unanalyzable
    )
    missing_params = sum(len(v) for v in param_gaps.values())

    return {
        "sdk_method_count": len(sdk),
        "covered_method_count": len(covered),
        "uncovered_methods": uncovered,
        "param_gaps": param_gaps,
        "unanalyzable": sorted(unanalyzable),
        "analyzed_param_count": total_params,
        "missing_param_count": missing_params,
        "_signatures": {
            m: [p for p in sdk[m].parameters if p != "self"] for m in uncovered
        },
    }


def load_baseline() -> dict[str, Any]:
    if not BASELINE.exists():
        return {"uncovered_methods": [], "param_gaps": {}, "unanalyzable": []}
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def write_baseline(result: dict[str, Any]) -> None:
    payload = {
        "_comment": (
            "Ratchet baseline for scripts/sdk_coverage.py. Known, accepted gaps "
            "between the monarchmoney SDK and the tools this server exposes. "
            "New entries may not be added without a deliberate update; entries "
            "that no longer reproduce must be removed. Regenerate with: "
            "uv run python scripts/sdk_coverage.py --update-baseline"
        ),
        "uncovered_methods": result["uncovered_methods"],
        "param_gaps": result["param_gaps"],
        "unanalyzable": result["unanalyzable"],
    }
    BASELINE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def diff_against_baseline(result: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (regressions, stale) messages comparing result to the baseline."""
    base = load_baseline()
    regressions: list[str] = []
    stale: list[str] = []

    cur_uncovered = set(result["uncovered_methods"])
    base_uncovered = set(base.get("uncovered_methods", []))
    for m in sorted(cur_uncovered - base_uncovered):
        regressions.append(f"SDK method no longer called anywhere: {m}()")
    for m in sorted(base_uncovered - cur_uncovered):
        stale.append(f"now covered, drop from baseline: {m}()")

    cur_gaps = result["param_gaps"]
    base_gaps = base.get("param_gaps", {})
    for method in sorted(set(cur_gaps) | set(base_gaps)):
        cur = set(cur_gaps.get(method, []))
        old = set(base_gaps.get(method, []))
        for p in sorted(cur - old):
            regressions.append(f"SDK param never passed: {method}(..., {p}=...)")
        for p in sorted(old - cur):
            stale.append(f"now passed, drop from baseline: {method}(..., {p}=...)")

    cur_un = set(result["unanalyzable"])
    base_un = set(base.get("unanalyzable", []))
    for m in sorted(cur_un - base_un):
        regressions.append(
            f"call became unanalyzable (**kwargs splat), params unchecked: {m}()"
        )
    for m in sorted(base_un - cur_un):
        stale.append(f"no longer uses a splat, drop from baseline: {m}()")

    return regressions, stale


def print_report(result: dict[str, Any]) -> None:
    sdk_n = result["sdk_method_count"]
    cov_n = result["covered_method_count"]
    print("=" * 66)
    print("SDK METHOD COVERAGE")
    print("=" * 66)
    print(f"  SDK public methods: {sdk_n}")
    print(f"  called from src/:   {cov_n}  ({cov_n / sdk_n:.0%})")
    if result["uncovered_methods"]:
        print("\n  Methods with no call site:")
        for m in result["uncovered_methods"]:
            params = ", ".join(result["_signatures"].get(m, []))
            print(f"    {m}({params})")

    print()
    print("=" * 66)
    print("SDK PARAMETER COVERAGE")
    print("=" * 66)
    total = result["analyzed_param_count"]
    missing = result["missing_param_count"]
    pct = (1 - missing / total) if total else 1.0
    print(f"  Params on analyzed methods: {total}")
    print(f"  Never passed anywhere:      {missing}  ({pct:.0%} covered)")
    if result["param_gaps"]:
        print()
        for method, params in sorted(result["param_gaps"].items()):
            print(f"    {method}: {', '.join(params)}")

    if result["unanalyzable"]:
        print()
        print("=" * 66)
        print("NOT STATICALLY ANALYZABLE (**kwargs splat at call site)")
        print("=" * 66)
        for m in result["unanalyzable"]:
            print(f"    {m}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if coverage drifts from the baseline in either direction",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="rewrite the baseline to match current coverage",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    result = analyze()

    if args.update_baseline:
        write_baseline(result)
        print(f"Baseline written to {BASELINE.relative_to(REPO_ROOT)}")
        return 0

    if args.json:
        payload = {k: v for k, v in result.items() if not k.startswith("_")}
        print(json.dumps(payload, indent=2))
        return 0

    if args.check:
        regressions, stale = diff_against_baseline(result)
        if not regressions and not stale:
            print("SDK coverage ratchet: OK (no drift from baseline)")
            return 0
        if regressions:
            print("SDK coverage REGRESSED - new gaps not in the baseline:\n")
            for msg in regressions:
                print(f"  - {msg}")
            print(
                "\nExpose the missing capability, or if the gap is deliberate, "
                "record it with:\n  uv run python scripts/sdk_coverage.py "
                "--update-baseline"
            )
        if stale:
            if regressions:
                print()
            print("SDK coverage IMPROVED - baseline is stale and must be tightened:\n")
            for msg in stale:
                print(f"  - {msg}")
            print(
                "\nThe ratchet only moves one way. Lock the improvement in with:\n"
                "  uv run python scripts/sdk_coverage.py --update-baseline"
            )
        return 1

    print_report(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
