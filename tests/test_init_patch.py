from monarchmoney import MonarchMoneyEndpoints


def test_base_url_patch():
    """Verify that MonarchMoneyEndpoints.BASE_URL is patched correctly."""
    # Import the package to trigger the patch

    # Check if the BASE_URL is set to the correct GraphQL endpoint
    assert MonarchMoneyEndpoints.BASE_URL == "https://api.monarch.com"
