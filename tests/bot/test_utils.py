from bot.claude import _provenance_footer, _round_currency

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
# _provenance_footer
# ---------------------------------------------------------------------------


def test_footer_empty_when_no_records():
    assert _provenance_footer([]) == ""


def test_footer_semantic_record():
    footer = _provenance_footer([
        {
            "source": "semantic",
            "model": "holdings_latest",
            "metrics": ["value_gbp", "weight_pct"],
            "group_by": ["fund_name"],
            "filters": ["account_name = ISA"],
            "time_range": None,
        }
    ])
    assert footer == (
        "📐 `semantic layer · holdings_latest · metrics: value_gbp, weight_pct"
        " · by: fund_name · filters: account_name = ISA`"
    )


def test_footer_sql_fallback_record():
    footer = _provenance_footer(
        [{"source": "sql_fallback", "tables": ["dim_fund", "mart_holdings_latest"]}]
    )
    assert footer == "🛠 `SQL fallback · tables: dim_fund, mart_holdings_latest`"


def test_footer_time_range_and_multiple_records():
    footer = _provenance_footer([
        {
            "source": "semantic",
            "model": "portfolio_value",
            "metrics": ["portfolio_value_gbp"],
            "group_by": [],
            "filters": [],
            "time_range": "2025-01-01 → 2025-12-31",
        },
        {"source": "sql_fallback", "tables": ["mart_benchmarks_monthly"]},
    ])
    lines = footer.splitlines()
    assert len(lines) == 2
    assert "2025-01-01 → 2025-12-31" in lines[0]
    assert lines[1].startswith("🛠")


def test_footer_dedupes_identical_records():
    record = {
        "source": "semantic",
        "model": "transactions",
        "metrics": ["fees_gbp"],
        "group_by": [],
        "filters": [],
        "time_range": None,
    }
    footer = _provenance_footer([record, dict(record)])
    assert len(footer.splitlines()) == 1
