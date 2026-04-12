from monarchmoney import MonarchMoneyEndpoints


def test_base_url_correct():
    """Verify that the community SDK has the correct BASE_URL natively."""
    assert MonarchMoneyEndpoints.BASE_URL == "https://api.monarch.com"
