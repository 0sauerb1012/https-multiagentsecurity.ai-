from handler import lambda_handler


def test_lambda_handler_returns_summary() -> None:
    result = lambda_handler(event={}, context=None)

    assert result["received"] >= 3
    assert result["normalized"] == result["received"]
    assert result["deduped"] <= result["normalized"]
