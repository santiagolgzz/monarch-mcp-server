"""Drift tests for the bundled Claude skill.

``.claude/skills/monarch-money-mcp/`` documents the tool surface for agents.
Nothing forced it to keep up with the code, and it didn't: between April and
September 2026 the server grew ``upload_attachment`` and ``get_credit_history``,
``create_transaction`` grew ``update_balance`` (the whole point of issue #15),
and the skill still described the old surface. An agent following it would have
written exactly the bug that was fixed.

These tests derive the truth from the registered tools and from
``SafetyConfig``'s defaults, then assert the skill's tables say the same thing.
Every failure message names the file to edit, because the fix is always to
update the skill, never to loosen the test.
"""

import ast
import asyncio
import re
from functools import lru_cache
from pathlib import Path

from fastmcp import FastMCP

from monarch_mcp_server.safety_config import SafetyConfig

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "monarch-money-mcp"
SKILL_MD = SKILL_DIR / "SKILL.md"
TOOLS_MD = SKILL_DIR / "references" / "tools.md"
SAFETY_MD = SKILL_DIR / "references" / "safety.md"
SRC_DIR = REPO_ROOT / "src" / "monarch_mcp_server"
TOOLS_DIR = SRC_DIR / "tools"

# Tools that change safety state rather than financial data. They are neither
# reads nor guarded writes, so they get their own label in the skill's tables.
ACTION_TOOLS = {"enable_emergency_stop", "disable_emergency_stop"}


# --------------------------------------------------------------------------
# Ground truth, derived from the code
# --------------------------------------------------------------------------


@lru_cache(maxsize=1)
def registered_tools() -> tuple[tuple[str, frozenset[str], frozenset[str]], ...]:
    """Return (name, params, required_params) per tool, in registration order.

    Built lazily rather than at import time so the autouse ``writable_fastmcp_home``
    fixture has already redirected FastMCP's state directory.
    """
    from monarch_mcp_server.tools import register_tools

    mcp = FastMCP("skill-accuracy-check")
    register_tools(mcp)
    tools = asyncio.run(mcp.list_tools())
    return tuple(
        (
            tool.name,
            frozenset(tool.parameters.get("properties", {})),
            frozenset(tool.parameters.get("required", [])),
        )
        for tool in tools
    )


def registered_names() -> list[str]:
    return [name for name, _, _ in registered_tools()]


def tool_schema(name: str) -> tuple[frozenset[str], frozenset[str]]:
    for tool_name, params, required in registered_tools():
        if tool_name == name:
            return params, required
    raise AssertionError(f"{name} is not a registered tool")


@lru_cache(maxsize=1)
def stdio_only_tools() -> frozenset[str]:
    """Tools declared directly on the stdio server, not via register_tools()."""
    tree = ast.parse((SRC_DIR / "server.py").read_text())
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            func = decorator.func if isinstance(decorator, ast.Call) else decorator
            # `@mcp.tool(...)`, or the `@annotated_tool(mcp)` wrapper that
            # registers a tool together with its MCP annotations.
            registers_a_tool = (
                isinstance(func, ast.Attribute)
                and func.attr == "tool"
                and isinstance(func.value, ast.Name)
                and func.value.id == "mcp"
            ) or (isinstance(func, ast.Name) and func.id == "annotated_tool")
            if registers_a_tool:
                names.add(node.name)
    return frozenset(names)


@lru_cache(maxsize=1)
def guarded_operations() -> frozenset[str]:
    """Operation names wrapped in @require_safety_check across tools/*.py."""
    names = set()
    for py_file in TOOLS_DIR.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "require_safety_check"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                names.add(node.args[0].value)
    return frozenset(names)


def safety_defaults() -> dict[str, list[str]]:
    """SafetyConfig's built-in defaults, independent of any user's config file."""
    config = SafetyConfig(config_path="/nonexistent/safety_config.json").config
    return {
        "approval": list(config["require_approval"]),
        "warn": list(config["warn_before_execute"]),
    }


def expected_tier(name: str) -> str:
    defaults = safety_defaults()
    if name in defaults["approval"]:
        return "Approval"
    if name in defaults["warn"]:
        return "Warn"
    if name in guarded_operations():
        return "Recorded"
    if name in ACTION_TOOLS:
        return "Action"
    return "Read"


# --------------------------------------------------------------------------
# Parsing the skill's tables
# --------------------------------------------------------------------------

_ROW = re.compile(r"^\|\s*(\d+|—)\s*\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*(\w+)\s*\|$")
_PARAM_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|[^|]*\|\s*(Yes|No)\s*\|")
_SECTION = re.compile(r"^## ([A-Za-z]+) \((\d+) tools?\)$", re.MULTILINE)
_CONTENTS = re.compile(r"^- ([A-Za-z]+) \((\d+)\) —", re.MULTILINE)


def tools_md_rows() -> list[tuple[str, str, str]]:
    """Return (number, tool_name, safety_label) for every tool row in tools.md."""
    rows = []
    for line in TOOLS_MD.read_text().splitlines():
        match = _ROW.match(line.strip())
        if match:
            rows.append((match.group(1), match.group(2), match.group(4)))
    return rows


def tools_md_param_table(tool_name: str) -> dict[str, bool]:
    """Return {param: required} from the '### <tool> Parameters' table."""
    text = TOOLS_MD.read_text()
    heading = f"### {tool_name} Parameters"
    assert heading in text, f"{TOOLS_MD.name} has no '{heading}' section"
    body = text.split(heading, 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]
    params = {}
    for line in body.splitlines():
        match = _PARAM_ROW.match(line.strip())
        if match:
            params[match.group(1)] = match.group(2) == "Yes"
    return params


def bullet_list_after(text: str, heading: str) -> list[str]:
    """Return the backticked items of the bullet list following a heading."""
    assert heading in text, f"missing heading: {heading}"
    body = text.split(heading, 1)[1].split("\n#", 1)[0]
    return re.findall(r"^- `([^`]+)`$", body, re.MULTILINE)


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


def test_skill_files_exist():
    for path in (SKILL_MD, TOOLS_MD, SAFETY_MD):
        assert path.exists(), f"missing skill file: {path}"


class TestToolsReference:
    """references/tools.md must list exactly the tools that exist."""

    def test_lists_every_registered_tool(self):
        documented = {name for _, name, _ in tools_md_rows()}
        expected = set(registered_names()) | stdio_only_tools()

        missing = expected - documented
        extra = documented - expected
        assert not missing, (
            f"{TOOLS_MD.name} is missing tools that exist: {sorted(missing)}. "
            "Add a row for each in the right section."
        )
        assert not extra, (
            f"{TOOLS_MD.name} documents tools that don't exist: {sorted(extra)}. "
            "Remove the rows or fix the names."
        )

    def test_numbering_matches_registration_order(self):
        numbered = [(n, name) for n, name, _ in tools_md_rows() if n != "—"]
        documented_order = [name for _, name in numbered]
        assert documented_order == registered_names(), (
            f"{TOOLS_MD.name} lists tools out of registration order.\n"
            f"expected: {registered_names()}\n"
            f"found:    {documented_order}"
        )

        expected_numbers = [str(i) for i in range(1, len(numbered) + 1)]
        assert [n for n, _ in numbered] == expected_numbers, (
            f"{TOOLS_MD.name} numbering is not a gapless 1..{len(numbered)} run. "
            "Renumber the tables after inserting or removing a tool."
        )

    def test_safety_labels_match_config(self):
        wrong = {
            name: (label, expected_tier(name))
            for _, name, label in tools_md_rows()
            if name not in stdio_only_tools() and label != expected_tier(name)
        }
        assert not wrong, (
            f"{TOOLS_MD.name} safety labels disagree with SafetyConfig "
            f"(tool: documented -> expected): {wrong}"
        )

    def test_section_counts_match_their_tables(self):
        text = TOOLS_MD.read_text()
        for section, claimed in _SECTION.findall(text):
            body = text.split(f"## {section} (", 1)[1].split("\n## ", 1)[0]
            actual = sum(1 for line in body.splitlines() if _ROW.match(line.strip()))
            assert int(claimed) == actual, (
                f"{TOOLS_MD.name}: '{section}' heading claims {claimed} tools "
                f"but its table has {actual}."
            )

    def test_contents_counts_match_section_headings(self):
        text = TOOLS_MD.read_text()
        headings = dict(_SECTION.findall(text))
        for section, claimed in _CONTENTS.findall(text):
            if section not in headings:
                continue
            assert claimed == headings[section], (
                f"{TOOLS_MD.name}: Contents says '{section} ({claimed})' but the "
                f"section heading says {headings[section]}."
            )


class TestParameterTables:
    """Parameter tables must match the tools' real signatures.

    This is the issue #15 class of drift: the tool grew an option and the docs
    kept describing the old signature.
    """

    def test_documented_tools_have_correct_params(self):
        text = TOOLS_MD.read_text()
        documented = re.findall(r"^### (\w+) Parameters$", text, re.MULTILINE)
        assert documented, f"{TOOLS_MD.name} has no parameter tables at all"

        for tool_name in documented:
            params, required = tool_schema(tool_name)
            table = tools_md_param_table(tool_name)

            missing = params - set(table)
            extra = set(table) - params
            assert not missing, (
                f"{TOOLS_MD.name}: '{tool_name} Parameters' omits real parameters "
                f"{sorted(missing)}. Agents won't know they exist."
            )
            assert not extra, (
                f"{TOOLS_MD.name}: '{tool_name} Parameters' documents parameters "
                f"that don't exist: {sorted(extra)}."
            )

            wrong = {
                param: (documented_required, param in required)
                for param, documented_required in table.items()
                if documented_required != (param in required)
            }
            assert not wrong, (
                f"{TOOLS_MD.name}: '{tool_name} Parameters' has the wrong Required "
                f"value (param: documented -> actual): {wrong}"
            )

    def test_update_balance_is_documented(self):
        """Pin the specific gap this suite was written for.

        ``create_transaction`` without ``update_balance`` is the bug from issue
        #15. The generic check above covers it, but name it explicitly so the
        regression can't slip back in behind a reshuffled table.
        """
        assert "update_balance" in tools_md_param_table("create_transaction"), (
            f"{TOOLS_MD.name} must document create_transaction's update_balance "
            "parameter — omitting it is the issue #15 bug."
        )
        assert "update_balance" in SKILL_MD.read_text(), (
            f"{SKILL_MD.name}'s 'Creating Transactions' section must mention "
            "update_balance."
        )


class TestSafetyReference:
    """references/safety.md tiers must match SafetyConfig's defaults."""

    def test_tier_1_matches_approval_list(self):
        documented = bullet_list_after(
            SAFETY_MD.read_text(), "### Tier 1: Destructive Operations"
        )
        assert sorted(documented) == sorted(safety_defaults()["approval"]), (
            f"{SAFETY_MD.name} Tier 1 disagrees with SafetyConfig's "
            f"require_approval list.\ndocumented: {sorted(documented)}\n"
            f"actual:     {sorted(safety_defaults()['approval'])}"
        )

    def test_tier_2_matches_warn_list(self):
        documented = bullet_list_after(
            SAFETY_MD.read_text(), "### Tier 2: Write Operations"
        )
        assert sorted(documented) == sorted(safety_defaults()["warn"]), (
            f"{SAFETY_MD.name} Tier 2 disagrees with SafetyConfig's "
            f"warn_before_execute list.\ndocumented: {sorted(documented)}\n"
            f"actual:     {sorted(safety_defaults()['warn'])}"
        )

    def test_tier_2b_matches_recorded_only_operations(self):
        defaults = safety_defaults()
        expected = (
            guarded_operations() - set(defaults["warn"]) - set(defaults["approval"])
        )
        documented = bullet_list_after(
            SAFETY_MD.read_text(), "### Tier 2b: Recorded-Only Write Operations"
        )
        assert sorted(documented) == sorted(expected), (
            f"{SAFETY_MD.name} Tier 2b disagrees with the guarded-but-unwarned "
            f"operations.\ndocumented: {sorted(documented)}\n"
            f"actual:     {sorted(expected)}"
        )


class TestSkillEntrypoint:
    """SKILL.md's headline claims must match reality."""

    def test_tool_count_is_correct(self):
        text = SKILL_MD.read_text()
        match = re.search(
            r"(\d+) tools for Monarch Money personal finance "
            r"\((\d+) shared \+ (\d+) stdio-only\)",
            text,
        )
        assert match, (
            f"{SKILL_MD.name} must state its tool count as "
            "'<N> tools for Monarch Money personal finance "
            "(<N> shared + <N> stdio-only).'"
        )
        total, shared, stdio = (int(g) for g in match.groups())
        assert shared == len(registered_names()), (
            f"{SKILL_MD.name} claims {shared} shared tools, "
            f"but {len(registered_names())} are registered."
        )
        assert stdio == len(stdio_only_tools()), (
            f"{SKILL_MD.name} claims {stdio} stdio-only tools, "
            f"but server.py declares {len(stdio_only_tools())}."
        )
        assert total == shared + stdio, (
            f"{SKILL_MD.name}'s total ({total}) is not {shared} + {stdio}."
        )

    def test_safety_bullets_match_config(self):
        text = SKILL_MD.read_text()
        defaults = safety_defaults()

        for label, key in (
            ("write ops show warnings", "warn"),
            ("destructive ops require a confirmation token", "approval"),
        ):
            match = re.search(rf"\*\*(\d+) {label}\*\* — (.+)", text)
            assert match, f"{SKILL_MD.name} has no '{label}' bullet"
            claimed_count = int(match.group(1))
            listed = re.findall(r"`([^`]+)`", match.group(2))
            expected = defaults[key]

            assert claimed_count == len(expected), (
                f"{SKILL_MD.name} says {claimed_count} {label}, "
                f"but SafetyConfig has {len(expected)}."
            )
            assert sorted(listed) == sorted(expected), (
                f"{SKILL_MD.name}'s '{label}' list disagrees with SafetyConfig.\n"
                f"documented: {sorted(listed)}\nactual:     {sorted(expected)}"
            )


def test_no_skill_file_references_a_nonexistent_tool():
    """Catch renamed or removed tools mentioned anywhere in the skill.

    Only checks backticked identifiers that look like tool calls, so prose and
    field names (``signedBalance``) don't trip it. Parameter names are allowed
    too — ``update_balance`` looks like a tool name but isn't one.
    """
    known = set(registered_names()) | stdio_only_tools()
    for _, params, _ in registered_tools():
        known |= set(params)
    verbs = (
        "get_",
        "create_",
        "update_",
        "delete_",
        "set_",
        "add_",
        "upload_",
        "search_",
        "is_",
        "check_",
        "refresh_",
        "request_",
        "enable_",
        "disable_",
        "categorize_",
    )

    bad: dict[str, set[str]] = {}
    for path in (
        SKILL_MD,
        TOOLS_MD,
        SAFETY_MD,
        SKILL_DIR / "references" / "financial-analysis.md",
    ):
        for token in re.findall(r"`([a-z_]+)(?:\([^`]*\))?`", path.read_text()):
            if token.startswith(verbs) and token not in known:
                bad.setdefault(path.name, set()).add(token)

    assert not bad, (
        "Skill files reference tools that don't exist: "
        f"{ {k: sorted(v) for k, v in bad.items()} }"
    )
