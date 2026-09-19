"""Check the golden fixtures against the SDK's real GraphQL documents.

``tests/sdk_fixtures.py`` exists because the old mocks described a response
shape the API never returns, which let a broken ``created_id`` extraction pass
its tests. Fixtures only help if they stay true, so this parses the mutation
documents out of the installed ``monarchmoney`` package and checks that each
fixture's envelope matches the selection set the SDK actually asks for.

If the SDK changes a mutation's shape, this fails and the fixture — and
whatever depends on it — gets updated, rather than the suite continuing to
agree with itself about a shape that no longer exists.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import monarchmoney
import pytest

from . import sdk_fixtures

SDK_SOURCE = (
    Path(inspect.getfile(monarchmoney)).resolve().parent / "monarchmoney.py"
).read_text()


def _operation_document(method_name: str) -> str:
    """Return the GraphQL document string used by an SDK method."""
    start = SDK_SOURCE.find(f"async def {method_name}(")
    assert start != -1, f"SDK has no method named {method_name}"

    # Stop at the next top-level method so we don't run into the next document.
    next_method = SDK_SOURCE.find("\n    async def ", start + 1)
    body = SDK_SOURCE[start : next_method if next_method != -1 else len(SDK_SOURCE)]

    match = re.search(r"\b(mutation|query)\s+\w+[^{]*\{", body)
    assert match, f"no GraphQL document found in {method_name}"
    return body[match.start() :]


def _name_of(raw: str) -> str:
    """Field name from a token, dropping arguments, aliases and directives."""
    return raw.strip().split("(")[0].split("@")[0].strip()


def _root_fields(document: str) -> dict[str, set[str]]:
    """Map each of the operation's root fields to its direct subfields.

    Queries may select several top-level fields — ``GetTransactionDrawer``
    asks for both ``getTransaction`` and ``myHousehold`` — so this returns all
    of them rather than assuming one. Walks braces rather than parsing GraphQL
    properly, which is enough to read a selection set and keeps the test free
    of a parser dependency.
    """
    open_brace = document.index("{")
    depth = 0
    current_root: str | None = None
    roots: dict[str, set[str]] = {}
    token = ""

    for char in document[open_brace:]:
        if char == "{":
            name = _name_of(token)
            depth += 1
            # depth is now the level of the selection set being opened, so the
            # name that preceded it sits one level up.
            if depth == 2 and name:
                current_root = name
                roots.setdefault(name, set())
            elif depth == 3 and name and current_root:
                # A child of a root that has its own selection set — the entity
                # wrappers (`transaction`, `account`, `errors`) live here, and
                # they are the whole point of these fixtures.
                roots[current_root].add(name)
            token = ""
        elif char == "}":
            if depth == 2 and _name_of(token) and current_root:
                roots[current_root].add(_name_of(token))
            depth -= 1
            token = ""
            if depth == 0:
                break
        elif char == "\n":
            if depth == 2 and _name_of(token) and current_root:
                roots[current_root].add(_name_of(token))
            token = ""
        else:
            token += char

    assert roots, f"could not find root fields in document: {document[:120]}"
    for children in roots.values():
        children.discard("")
    return roots


# (fixture callable, SDK method whose document defines the shape)
MUTATION_FIXTURES = [
    (sdk_fixtures.create_transaction_response, "create_transaction"),
    (sdk_fixtures.create_manual_account_response, "create_manual_account"),
    (sdk_fixtures.create_category_response, "create_transaction_category"),
    (sdk_fixtures.create_tag_response, "create_transaction_tag"),
    (sdk_fixtures.delete_transaction_response, "delete_transaction"),
]

# Read queries matter just as much: `get_budgets` returns `budgetData`, but the
# tool read a top-level `budgets` key and so always returned an empty list. The
# mock agreed with the tool, so the suite never noticed.
QUERY_FIXTURES = [
    (sdk_fixtures.budgets_response, "get_budgets"),
    (sdk_fixtures.transaction_splits_response, "get_transaction_splits"),
    (sdk_fixtures.transaction_detail, "get_transaction_details"),
]


@pytest.mark.parametrize(
    ("fixture", "sdk_method"),
    MUTATION_FIXTURES,
    ids=[method for _, method in MUTATION_FIXTURES],
)
def test_fixture_envelope_matches_sdk_document(fixture, sdk_method):
    """The fixture's envelope must match what the SDK's document selects."""
    roots = _root_fields(_operation_document(sdk_method))
    assert len(roots) == 1, f"{sdk_method} is expected to have one root field"
    root_field, selected = next(iter(roots.items()))

    payload = fixture()
    assert list(payload) == [root_field], (
        f"{fixture.__name__} wraps its payload in {list(payload)}, but "
        f"{sdk_method}'s document returns it under '{root_field}'."
    )

    # Ignore GraphQL bookkeeping and fragment spreads.
    expected = {
        name
        for name in selected
        if not name.startswith(("...", "__")) and name.isidentifier()
    }
    present = set(payload[root_field])
    missing = expected - present
    assert not missing, (
        f"{fixture.__name__} omits fields {sorted(missing)} that "
        f"{sdk_method} selects. The fixture no longer matches the real shape."
    )


@pytest.mark.parametrize(
    ("fixture", "sdk_method"),
    QUERY_FIXTURES,
    ids=[method for _, method in QUERY_FIXTURES],
)
def test_query_fixture_root_matches_sdk_document(fixture, sdk_method):
    """A read fixture must be keyed by the field the query actually selects."""
    roots = _root_fields(_operation_document(sdk_method))

    payload = fixture()
    assert set(payload) <= set(roots), (
        f"{fixture.__name__} keys its payload as {sorted(payload)}, but "
        f"{sdk_method} selects {sorted(roots)}. Reading a key the query does "
        "not return is what made get_budgets always give an empty list."
    )


def test_fixtures_are_actually_nested():
    """Guard the specific mistake these fixtures replace.

    A flat ``{"id": ...}`` is what the old mocks used and what made the
    extraction bug invisible. No create fixture may be flat.
    """
    for fixture, sdk_method in MUTATION_FIXTURES:
        payload = fixture()
        assert "id" not in payload, (
            f"{fixture.__name__} puts 'id' at the top level. {sdk_method} "
            "returns a GraphQL envelope, so a flat shape is the fiction these "
            "fixtures exist to prevent."
        )
