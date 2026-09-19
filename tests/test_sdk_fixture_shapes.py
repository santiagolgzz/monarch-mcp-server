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


def _root_field_and_children(document: str) -> tuple[str, set[str]]:
    """Extract the operation's root field name and its direct subfields.

    Walks braces rather than parsing GraphQL properly — enough to read a
    selection set, and it keeps the test free of a parser dependency.
    """
    # Skip past `mutation Name(...) {` to the operation's selection set.
    open_brace = document.index("{")
    depth = 0
    root_name: str | None = None
    children: set[str] = set()
    token = ""

    def name_of(raw: str) -> str:
        """Field name from a token, dropping any argument list or alias."""
        return raw.strip().split("(")[0].strip()

    for char in document[open_brace:]:
        if char == "{":
            name = name_of(token)
            depth += 1
            # depth is now the level of the selection set being opened, so the
            # name that preceded it sits one level up.
            if depth == 2 and name:
                root_name = name
            elif depth == 3 and name:
                # A child of the root that has its own selection set — the
                # entity wrappers (`transaction`, `account`, `errors`) live
                # here, and they are the whole point of these fixtures.
                children.add(name)
            token = ""
        elif char == "}":
            if depth == 2 and name_of(token):
                children.add(name_of(token))
            depth -= 1
            token = ""
            if depth == 0:
                break
        elif char == "\n":
            if depth == 2 and name_of(token):
                children.add(name_of(token))
            token = ""
        else:
            token += char

    assert root_name, f"could not find root field in document: {document[:120]}"
    children.discard("")
    return root_name, children


# (fixture callable, SDK method whose document defines the shape)
MUTATION_FIXTURES = [
    (sdk_fixtures.create_transaction_response, "create_transaction"),
    (sdk_fixtures.create_manual_account_response, "create_manual_account"),
    (sdk_fixtures.create_category_response, "create_transaction_category"),
    (sdk_fixtures.create_tag_response, "create_transaction_tag"),
    (sdk_fixtures.delete_transaction_response, "delete_transaction"),
]


@pytest.mark.parametrize(
    ("fixture", "sdk_method"),
    MUTATION_FIXTURES,
    ids=[method for _, method in MUTATION_FIXTURES],
)
def test_fixture_envelope_matches_sdk_document(fixture, sdk_method):
    """The fixture's envelope must match what the SDK's document selects."""
    document = _operation_document(sdk_method)
    root_field, selected = _root_field_and_children(document)

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
