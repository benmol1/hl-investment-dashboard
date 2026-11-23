"""Parse the Barratt & Cooke ledger PDF for the PELM Will Trust into a transactions CSV.

    uv run python backend/scripts/parse_pelm_ledger.py [LEDGER_PDF] [OUT_CSV]

With no arguments it looks for "C070982 Ledger statements.pdf" in pelm-inputs/ (on a laptop) and
then in data/pelm/ (on the server, where only data/ is mounted), and writes
data/pelm/pelm_transactions.csv. In the cron container:

    docker compose exec cron /app/.venv/bin/python backend/scripts/parse_pelm_ledger.py

The ledger is read by word position (debit amounts are right-aligned under one column header,
credits under another), which is reliable where plain text extraction shuffles the columns.
Nothing is written unless the ledger reconciles: opening balance + credits - debits must equal
the closing balance. Afterwards the external flows found in the ledger are compared with the
external_flow_gbp column of data/pelm/pelm_monthly.csv, and any difference is reported.

Output columns: tx_date, reference, tx_type, security, quantity, amount_gbp, notes.
amount_gbp is the cash effect on the ledger: positive for money in, negative for money out,
blank where there is none (in-specie transfers, corporate actions). The first row is the
OPENING_BALANCE of the cash ledger.
"""

import collections
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

import pdfplumber

REPO = Path(__file__).resolve().parents[2]
LEDGER_NAME = "C070982 Ledger statements.pdf"
DEFAULT_PDF_LOCATIONS = [
    REPO / "pelm-inputs" / LEDGER_NAME,
    REPO / "data" / "pelm" / LEDGER_NAME,
]
DEFAULT_OUT = REPO / "data" / "pelm" / "pelm_transactions.csv"
MONTHLY_CSV = REPO / "data" / "pelm" / "pelm_monthly.csv"

DATE_RE = re.compile(r"^\d{2}-[A-Z][a-z]{2}-\d{4}$")
AMOUNT_RE = re.compile(r"^-?[\d,]+\.\d{2}$")
QTY_NAME_RE = re.compile(r"^([\d,]+(?:\.\d+)?)\s+(.+)$")
FX_RE = re.compile(r"^GBP/[A-Z]{3}\s+[\d.]+$")

# Column geometry (PDF points): narrative text starts at x=215; amounts start right of x=380.
# Debit amounts end near x=461 and credit amounts near x=531.
NARRATIVE_MIN_X, AMOUNT_MIN_X, CREDIT_MIN_X1 = 215, 380, 500
DATE_MAX_X = 100  # a row starts with a date whose left edge is at x<100

FIELDS = [
    "tx_date",
    "reference",
    "tx_type",
    "security",
    "quantity",
    "amount_gbp",
    "notes",
]


def read_entries(pdf_path: Path) -> list[dict]:
    """One dict per ledger entry: date, reference, narrative line(s), debit, credit, detail lines."""
    entries: list[dict] = []
    current = None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            lines = collections.defaultdict(list)
            for word in page.extract_words():
                lines[round(word["top"])].append(word)
            for top in sorted(lines):
                words = sorted(lines[top], key=lambda w: w["x0"])
                starts_entry = words[0]["x0"] < DATE_MAX_X and DATE_RE.match(
                    words[0]["text"]
                )
                if starts_entry:
                    current = {
                        "date": words[0]["text"],
                        "reference": next(
                            (w["text"] for w in words if 120 < w["x0"] < 200), None
                        ),
                        "narrative": "",
                        "debit": None,
                        "credit": None,
                        "detail": [],
                    }
                    entries.append(current)
                if current is None:
                    continue  # page header before the first entry
                text = " ".join(
                    w["text"]
                    for w in words
                    if w["x0"] > NARRATIVE_MIN_X
                    and not (AMOUNT_RE.match(w["text"]) and w["x0"] > AMOUNT_MIN_X)
                )
                for w in words:
                    if AMOUNT_RE.match(w["text"]) and w["x0"] > AMOUNT_MIN_X:
                        value = float(w["text"].replace(",", ""))
                        side = "credit" if w["x1"] > CREDIT_MIN_X1 else "debit"
                        current[side] = value
                if starts_entry:
                    current["narrative"] = text
                elif text:
                    current["detail"].append(text)
    return entries


def classify(entry: dict) -> list[dict]:
    """Turn one ledger entry into one or more output rows."""
    narrative, detail = entry["narrative"], entry["detail"]
    debit, credit = entry["debit"], entry["credit"]
    amount = credit if credit is not None else (-debit if debit is not None else None)
    base = {
        "reference": entry["reference"],
        "quantity": None,
        "security": "",
        "notes": "",
    }
    date = datetime.strptime(entry["date"], "%d-%b-%Y").date().isoformat()

    def row(tx_type, **kw):
        return {"tx_date": date, **base, "tx_type": tx_type, "amount_gbp": amount, **kw}

    fx_notes = "; ".join(d for d in detail if FX_RE.match(d))

    trade = re.match(r"^(BT|SD)\s+([\d,]+(?:\.\d+)?)\s+(.+)$", narrative)
    if trade:
        code, qty, name = trade.groups()
        return [
            row(
                "BUY" if code == "BT" else "SELL",
                quantity=float(qty.replace(",", "")),
                security=name,
                notes=fx_notes,
            )
        ]
    if narrative.startswith("TRANSFERRED TO DEPOSIT"):
        return [row("DEPOSIT_TRANSFER_OUT")]
    if narrative.startswith("TRANSFERRED FROM DEPOSIT"):
        return [row("DEPOSIT_TRANSFER_IN")]
    if narrative.startswith("TRANSFER FROM"):
        return [row("CASH_TRANSFER_IN", notes=narrative)]
    if narrative.startswith("BACS Payment"):
        return [row("WITHDRAWAL", notes=narrative)]
    if narrative.startswith("CASH FRACTION"):
        return [
            row(
                "CASH_FRACTION",
                security=narrative.removeprefix("CASH FRACTION ").strip(),
            )
        ]
    if narrative.startswith("STOCK TRANSFERRED IN"):
        # First detail line names the source account; each later line is "<quantity> <security>".
        source = " ".join(filter(None, [narrative, detail[0] if detail else ""]))
        rows = []
        for line in detail[1:]:
            m = QTY_NAME_RE.match(line)
            if not m:
                raise ValueError(f"Unrecognised stock transfer line: {line!r}")
            rows.append(
                row(
                    "STOCK_TRANSFER_IN",
                    quantity=float(m.group(1).replace(",", "")),
                    security=m.group(2),
                    notes=source,
                    amount_gbp=None,
                )
            )
        return rows
    if amount is None:
        # No cash and no recognised cash narrative: a corporate action (demerger, name change...).
        return [row("CORPORATE_ACTION", security=narrative, notes=" ".join(detail))]
    return [row("OTHER", security=narrative, notes=" ".join(detail))]


def reconcile(entries: list[dict]) -> tuple[list[dict], float, float, float, float]:
    """Split off the opening/closing balance entries and check the ledger adds up."""
    opening = closing = None
    body = []
    for e in entries:
        value = e["credit"] if e["credit"] is not None else e["debit"]
        if e["narrative"].startswith("Opening balance"):
            opening = value
        elif e["narrative"].startswith("Closing balance"):
            closing = value
        else:
            body.append(e)
    if opening is None or closing is None:
        raise ValueError("Could not find the opening and closing balance rows")
    credits = sum(e["credit"] or 0.0 for e in body)
    debits = sum(e["debit"] or 0.0 for e in body)
    return body, opening, closing, credits, debits


def external_flows_by_month(rows: list[dict]) -> dict[str, float]:
    flows: dict[str, float] = collections.defaultdict(float)
    for r in rows:
        if (
            r["tx_type"] in ("CASH_TRANSFER_IN", "WITHDRAWAL")
            and r["amount_gbp"] is not None
        ):
            flows[r["tx_date"][:7]] += r["amount_gbp"]
    return {k: round(v, 2) for k, v in flows.items()}


def compare_with_monthly(flows: dict[str, float]) -> list[str]:
    """Compare ledger external flows with the hand-entered column in pelm_monthly.csv."""
    if not MONTHLY_CSV.exists():
        return [f"(skipped flow check: {MONTHLY_CSV} not found)"]
    with MONTHLY_CSV.open() as f:
        monthly = list(csv.DictReader(f))
    if not monthly:
        return ["(skipped flow check: pelm_monthly.csv is empty)"]
    first_month = monthly[0]["month_end_date"][:7]
    entered = {
        r["month_end_date"][:7]: float(r["external_flow_gbp"] or 0) for r in monthly
    }
    problems = []
    # The first month's flow is inside the opening valuation, so it is not compared.
    for month in sorted((set(flows) | set(entered)) - {first_month}):
        if month < first_month:
            continue
        ledger, seed = flows.get(month, 0.0), entered.get(month, 0.0)
        if abs(ledger - seed) > 0.005:
            problems.append(
                f"{month}: ledger {ledger:,.2f} vs pelm_monthly.csv {seed:,.2f}"
            )
    return problems


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        pdf_path = Path(argv[1])
    else:
        pdf_path = next(
            (p for p in DEFAULT_PDF_LOCATIONS if p.exists()), DEFAULT_PDF_LOCATIONS[0]
        )
    out_path = Path(argv[2]) if len(argv) > 2 else DEFAULT_OUT
    if not pdf_path.exists():
        looked = (
            ", ".join(str(p) for p in DEFAULT_PDF_LOCATIONS)
            if len(argv) <= 1
            else str(pdf_path)
        )
        print(f"Ledger PDF not found (looked in: {looked})", file=sys.stderr)
        return 1

    entries = read_entries(pdf_path)
    body, opening, closing, credits, debits = reconcile(entries)
    expected_close = round(opening + credits - debits, 2)
    if abs(expected_close - closing) > 0.005:
        print(
            f"Ledger does NOT reconcile: opening {opening:,.2f} + credits {credits:,.2f} "
            f"- debits {debits:,.2f} = {expected_close:,.2f}, but closing balance is {closing:,.2f}. "
            "Nothing written.",
            file=sys.stderr,
        )
        return 1

    rows = [r for e in body for r in classify(e)]
    # The opening balance is kept as a row so cash at any month-end can be rebuilt downstream.
    opening_date = next(
        e["date"] for e in entries if e["narrative"].startswith("Opening balance")
    )
    rows.insert(
        0,
        {
            "tx_date": datetime.strptime(opening_date, "%d-%b-%Y").date().isoformat(),
            "reference": None,
            "tx_type": "OPENING_BALANCE",
            "security": "",
            "quantity": None,
            "amount_gbp": opening,
            "notes": "Ledger opening cash balance",
        },
    )
    other = [r for r in rows if r["tx_type"] == "OTHER"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: ("" if r[k] is None else r[k]) for k in FIELDS})

    print(
        f"Reconciled: opening {opening:,.2f} + credits {credits:,.2f} - debits {debits:,.2f} "
        f"= closing {closing:,.2f}"
    )
    print(f"Wrote {len(rows)} rows to {out_path}")
    for tx_type, n in sorted(collections.Counter(r["tx_type"] for r in rows).items()):
        print(f"  {tx_type:22} {n}")
    for r in other:
        print(
            f"  note: unclassified entry kept as OTHER: {r['tx_date']} {r['security']}"
        )

    problems = compare_with_monthly(external_flows_by_month(rows))
    if problems:
        print("External flow differences vs pelm_monthly.csv:")
        for p in problems:
            print(f"  {p}")
    else:
        print("External flows agree with pelm_monthly.csv.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
