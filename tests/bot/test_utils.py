from bot.claude import _round_currency
from bot.executors import _summarise_series


# ---------------------------------------------------------------------------
# _round_currency
# ---------------------------------------------------------------------------


def test_round_currency_below_threshold_unchanged():
    assert _round_currency("£5.99") == "£5.99"


def test_round_currency_just_below_threshold_unchanged():
    assert _round_currency("£9.99") == "£9.99"


def test_round_currency_at_threshold_rounded():
    # Python round() uses banker's rounding: round(10.5) → 10 (nearest even)
    assert _round_currency("£10.50") == "£10"
    assert _round_currency("£11.50") == "£12"


def test_round_currency_large_amount_rounded():
    assert _round_currency("£1,234.56") == "£1,235"


def test_round_currency_no_pound_sign_passthrough():
    assert _round_currency("100.00") == "100.00"


def test_round_currency_mixed_text():
    result = _round_currency("Portfolio: £9.50 cash, £1,500.00 funds")
    assert "£9.50" in result
    assert "£1,500" in result
    assert "£1,500.00" not in result


# ---------------------------------------------------------------------------
# _summarise_series
# ---------------------------------------------------------------------------


def test_summarise_series_empty():
    assert _summarise_series([], "date") == []


def test_summarise_series_short_list_unchanged():
    points = [{"date": f"2024-{m:02d}-01", "value": m} for m in range(1, 13)]
    result = _summarise_series(points, "date")
    assert len(result) == 12


def test_summarise_series_dedupes_by_month():
    # Two points in the same month — last one should win
    points = [
        {"date": "2024-01-15", "value": 1},
        {"date": "2024-01-31", "value": 2},
        {"date": "2024-02-28", "value": 3},
    ]
    result = _summarise_series(points, "date")
    assert len(result) == 2
    assert result[0]["value"] == 2  # last Jan point
    assert result[1]["value"] == 3
