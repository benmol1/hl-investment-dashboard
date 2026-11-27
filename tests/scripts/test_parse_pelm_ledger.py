"""Unit tests for the PELM ledger parser's classification and statement merging (no PDFs)."""

import importlib.util
from datetime import date
from pathlib import Path

import pytest

_PATH = (
    Path(__file__).resolve().parents[2] / "backend" / "scripts" / "parse_pelm_ledger.py"
)
_spec = importlib.util.spec_from_file_location("parse_pelm_ledger", _PATH)
parser = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parser)


def entry(
    narrative, debit=None, credit=None, date_="01-Jul-2025", ref="R1", detail=None
):
    return {
        "date": date_,
        "reference": ref,
        "narrative": narrative,
        "debit": debit,
        "credit": credit,
        "detail": detail or [],
    }


@pytest.mark.parametrize(
    "narrative, ledger, debit, credit, tx_type, security",
    [
        ("DIV ON ASTRAZENECA", "dividends", None, 263.08, "DIVIDEND", "ASTRAZENECA"),
        (
            'FX COMM-NIKE INC CLS "B"',
            "dividends",
            0.45,
            None,
            "FX_COMMISSION",
            'NIKE INC CLS "B"',
        ),
        (
            "FX COMM ASML HOLDING NV",
            "dividends",
            0.40,
            None,
            "FX_COMMISSION",
            "ASML HOLDING NV",
        ),
        ("BACS Payment", "dividends", 279.35, None, "INCOME_DISTRIBUTION", ""),
        ("BACS Payment *3850", "capital", 157000.0, None, "WITHDRAWAL", ""),
        ("INT (GROSS) T/FER", "income", None, 2.23, "INTEREST", ""),
        ("INTEREST (GROSS) <", "income", None, 2.74, "INTEREST", ""),
        ("*TO SETTLEMENT", "income", 2020.08, None, "SETTLEMENT_TRANSFER", ""),
        ("TO SETTLEMENT", "capital", 108.0, None, "SETTLEMENT_TRANSFER", ""),
        ("CUSTODY MANAGEMENT FEE", "fees", 750.0, None, "FEE", ""),
        ("VAT ON CUSTODY MAN FEE", "fees", 150.0, None, "FEE_VAT", ""),
        ("TRANSFERRED FROM DEPOSIT", "fees", None, 900.0, "DEPOSIT_TRANSFER_IN", ""),
        (
            "TRANSFERRED TO DEPOSIT",
            "dividends",
            454.55,
            None,
            "DEPOSIT_TRANSFER_OUT",
            "",
        ),
        (
            "BT 8100 LONDONMETRIC PROP",
            "capital",
            14998.66,
            None,
            "BUY",
            "LONDONMETRIC PROP",
        ),
        ("SD 350 SHELL PLC", "capital", None, 9008.57, "SELL", "SHELL PLC"),
    ],
)
def test_classify(narrative, ledger, debit, credit, tx_type, security):
    [row] = parser.classify(entry(narrative, debit, credit), ledger)
    assert row["tx_type"] == tx_type
    assert row["security"] == security
    assert row["ledger"] == ledger
    assert row["amount_gbp"] == (credit if credit is not None else -debit)


def statement(ledger, start, end, opening, closing, entries, source="a.pdf"):
    s = {
        "ledger": ledger,
        "period_start": start,
        "period_end": end,
        "source_file": source,
        "entries": [
            entry("Opening balance", credit=opening),
            *entries,
            entry("Closing balance", credit=closing),
        ],
    }
    parser.reconcile(s)
    return s


def test_reconcile_rejects_a_statement_that_does_not_add_up():
    with pytest.raises(ValueError, match="does NOT reconcile"):
        statement(
            "dividends",
            date(2025, 7, 1),
            date(2025, 9, 30),
            100.0,
            50.0,
            [entry("DIV ON X", credit=10.0)],
        )


def test_combine_drops_entries_repeated_in_overlapping_statements():
    trade = entry("SD 10 ACME", credit=500.0, date_="15-Aug-2025", ref="S1")
    sweep = entry("TRANSFERRED TO DEPOSIT", debit=500.0, date_="16-Aug-2025", ref="T1")
    long = statement(
        "capital",
        date(2023, 9, 4),
        date(2026, 6, 4),
        0.0,
        0.0,
        [trade, sweep],
        "all.pdf",
    )
    quarter = statement(
        "capital",
        date(2025, 7, 1),
        date(2025, 9, 30),
        0.0,
        0.0,
        [trade, sweep],
        "q3.pdf",
    )
    rows, coverage = parser.combine([quarter, long])
    assert [r["tx_type"] for r in rows] == [
        "OPENING_BALANCE",
        "SELL",
        "DEPOSIT_TRANSFER_OUT",
    ]
    assert len(coverage) == 2


def test_combine_checks_opening_balances_of_contiguous_statements():
    q3 = statement(
        "dividends",
        date(2025, 7, 1),
        date(2025, 9, 30),
        100.0,
        110.0,
        [entry("DIV ON X", credit=10.0, date_="05-Aug-2025")],
    )
    q4_bad = statement(
        "dividends", date(2025, 10, 1), date(2025, 12, 31), 999.0, 999.0, []
    )
    with pytest.raises(ValueError, match="does not match"):
        parser.combine([q3, q4_bad])


def test_combine_carries_a_gap_between_statements_as_a_balance_adjustment():
    q3 = statement(
        "dividends",
        date(2025, 7, 1),
        date(2025, 9, 30),
        100.0,
        110.0,
        [entry("DIV ON X", credit=10.0, date_="05-Aug-2025")],
    )
    q1 = statement("dividends", date(2026, 1, 1), date(2026, 3, 31), 150.0, 150.0, [])
    rows, _ = parser.combine([q3, q1])
    adjustment = [r for r in rows if r["tx_type"] == "BALANCE_ADJUSTMENT"]
    assert len(adjustment) == 1
    assert adjustment[0]["tx_date"] == "2026-01-01"
    assert adjustment[0]["amount_gbp"] == 40.0
    # Opening + movements + adjustment equal the latest closing balance.
    assert round(sum(r["amount_gbp"] or 0 for r in rows), 2) == 150.0
