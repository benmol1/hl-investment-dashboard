"""Parse the Barratt & Cooke ledger PDFs for the PELM Will Trust into a transactions CSV.

    uv run python backend/scripts/parse_pelm_ledger.py [PDF_OR_DIR ...] [--out-dir DIR]

With no inputs it reads every "C070982 Ledger*.pdf" under pelm-inputs/ (on a laptop) or, if
there are none, under data/pelm/ (on the server, where only data/ is mounted). Subfolders are
searched, so each quarterly pack can stay in its own dated folder. In the cron container:

    docker compose exec cron /app/.venv/bin/python backend/scripts/parse_pelm_ledger.py

Each PDF holds one or more statements, one per sub-ledger, each with its own opening and
closing balance:

    capital    C070982  General Investment Account ledger: trades, deposit sweeps, withdrawals
    dividends  E070982  GIA dividends and claims ledger: dividends, FX commission, BACS income
                        payments to the beneficiary
    income     t070982  GIA income account ledger: interest, settlement transfers
    fees       d070982  Fees ledger: custody fee and VAT

Statements may overlap (the first pack's capital ledger runs Sep 2023 - Jun 2026; later packs
are quarterly); duplicate entries are dropped. Lines are read by word position (debits sit
under one column header, credits under another). Nothing is written unless every statement
reconciles (opening + credits - debits = closing) and each statement's opening balance agrees
with the entries already seen for that ledger. Where there is a gap between two statements of
the same ledger, a BALANCE_ADJUSTMENT row carries the unseen net movement.

Writes two files to data/pelm/:

  pelm_transactions.csv  ledger, tx_date, reference, tx_type, security, quantity, amount_gbp, notes
      amount_gbp is the cash effect on that ledger: positive in, negative out, blank where there
      is none (in-specie transfers, corporate actions). Each ledger starts with an
      OPENING_BALANCE row.
  pelm_ledger_coverage.csv  ledger, period_start, period_end, opening_gbp, closing_gbp, source_file
      One row per statement. dbt uses it to tell which months have a complete set of cash flows.
"""

import argparse
import collections
import csv
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pdfplumber

REPO = Path(__file__).resolve().parents[2]
PDF_GLOB = "C070982 Ledger*.pdf"
DEFAULT_SEARCH_DIRS = [REPO / "pelm-inputs", REPO / "data" / "pelm"]
DEFAULT_OUT_DIR = REPO / "data" / "pelm"

DATE_RE = re.compile(r"^\d{2}-[A-Z][a-z]{2}-\d{4}$")
AMOUNT_RE = re.compile(r"^-?[\d,]+\.\d{2}$")
QTY_NAME_RE = re.compile(r"^([\d,]+(?:\.\d+)?)\s+(.+)$")
FX_RE = re.compile(r"^GBP/[A-Z]{3}\s+[\d.]+$")
PERIOD_RE = re.compile(
    r"statement for (\d{1,2} [A-Z][a-z]{2} \d{4}) to (\d{1,2} [A-Z][a-z]{2} \d{4})"
)

# Statement heading -> ledger name. Checked in order, so the longer GIA headings come first.
LEDGER_HEADINGS = [
    ("GIA dividends and claims ledger", "dividends"),
    ("GIA income account ledger", "income"),
    ("Fees ledger", "fees"),
    ("General Investment Account ledger", "capital"),
]

# Column geometry (PDF points): narrative text starts at x=215; amounts start right of x=380.
# Debit amounts end near x=461 and credit amounts near x=531.
NARRATIVE_MIN_X, AMOUNT_MIN_X, CREDIT_MIN_X1 = 215, 380, 500
DATE_MAX_X = 100  # a row starts with a date whose left edge is at x<100

FIELDS = [
    "ledger",
    "tx_date",
    "reference",
    "tx_type",
    "security",
    "quantity",
    "amount_gbp",
    "notes",
]
COVERAGE_FIELDS = [
    "ledger",
    "period_start",
    "period_end",
    "opening_gbp",
    "closing_gbp",
    "source_file",
]


def _iso(ledger_date: str) -> str:
    return datetime.strptime(ledger_date, "%d-%b-%Y").date().isoformat()


def read_statements(pdf_path: Path) -> list[dict]:
    """Split a PDF into statements: ledger, period, opening, closing and the entries between."""
    statements: list[dict] = []
    statement = None
    current = None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            heading = next(
                (line for line in text.splitlines() if PERIOD_RE.search(line)), None
            )
            if heading is None:
                raise ValueError(
                    f"{pdf_path.name}: page {page.page_number} has no statement heading"
                )
            ledger = next(
                (name for key, name in LEDGER_HEADINGS if key in heading), None
            )
            if ledger is None:
                raise ValueError(
                    f"{pdf_path.name}: unrecognised ledger heading {heading!r}"
                )
            start, end = (
                datetime.strptime(d, "%d %b %Y").date()
                for d in PERIOD_RE.search(heading).groups()
            )
            if statement is None or (
                statement["ledger"],
                statement["period_start"],
            ) != (ledger, start):
                statement = {
                    "ledger": ledger,
                    "period_start": start,
                    "period_end": end,
                    "source_file": pdf_path.name,
                    "entries": [],
                }
                statements.append(statement)
                current = None

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
                    statement["entries"].append(current)
                if current is None:
                    continue  # page header before the first entry
                line_text = " ".join(
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
                    current["narrative"] = line_text
                elif line_text and not line_text.startswith("Page "):
                    current["detail"].append(line_text)
    for s in statements:
        reconcile(s)
    return statements


def reconcile(statement: dict) -> None:
    """Split off the opening/closing balance entries and check the statement adds up."""
    opening = closing = None
    body = []
    for e in statement["entries"]:
        value = e["credit"] if e["credit"] is not None else (e["debit"] or 0.0)
        if e["narrative"].startswith("Opening balance"):
            # A debit opening balance would be an overdrawn ledger.
            opening = (
                -value
                if e["debit"] is not None and e["credit"] is None and value
                else value
            )
        elif e["narrative"].startswith("Closing balance"):
            closing = (
                -value
                if e["debit"] is not None and e["credit"] is None and value
                else value
            )
        else:
            body.append(e)
    name = (
        f"{statement['source_file']} {statement['ledger']} {statement['period_start']}"
    )
    if opening is None or closing is None:
        raise ValueError(f"{name}: could not find the opening and closing balance rows")
    credits = sum(e["credit"] or 0.0 for e in body)
    debits = sum(e["debit"] or 0.0 for e in body)
    expected = round(opening + credits - debits, 2)
    if abs(expected - closing) > 0.005:
        raise ValueError(
            f"{name} does NOT reconcile: opening {opening:,.2f} + credits {credits:,.2f} "
            f"- debits {debits:,.2f} = {expected:,.2f}, but closing balance is {closing:,.2f}"
        )
    statement.update(
        entries=body, opening=opening, closing=closing, credits=credits, debits=debits
    )


def classify(entry: dict, ledger: str) -> list[dict]:
    """Turn one ledger entry into one or more output rows."""
    narrative, detail = entry["narrative"], entry["detail"]
    debit, credit = entry["debit"], entry["credit"]
    amount = credit if credit is not None else (-debit if debit is not None else None)
    base = {
        "ledger": ledger,
        "reference": entry["reference"],
        "quantity": None,
        "security": "",
        "notes": "",
    }
    tx_date = _iso(entry["date"])

    def row(tx_type, **kw):
        return {
            "tx_date": tx_date,
            **base,
            "tx_type": tx_type,
            "amount_gbp": amount,
            **kw,
        }

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
    if narrative.startswith("DIV ON "):
        return [
            row(
                "DIVIDEND",
                security=narrative.removeprefix("DIV ON ").strip(),
                notes=" ".join(detail),
            )
        ]
    if narrative.startswith("FX COMM"):
        return [
            row(
                "FX_COMMISSION",
                security=re.sub(r"^FX COMM[- ]?", "", narrative).strip(),
            )
        ]
    if narrative.startswith(("INTEREST (GROSS)", "INT (GROSS)")):
        return [row("INTEREST", notes=narrative)]
    if narrative.startswith("VAT ON"):
        return [row("FEE_VAT", notes=narrative)]
    if "FEE" in narrative and ledger == "fees":
        return [row("FEE", notes=narrative)]
    if narrative.lstrip("*").startswith(("TO SETTLEMENT", "FROM SETTLEMENT")):
        return [row("SETTLEMENT_TRANSFER", notes=narrative)]
    if narrative.startswith("TRANSFERRED TO DEPOSIT"):
        return [row("DEPOSIT_TRANSFER_OUT")]
    if narrative.startswith("TRANSFERRED FROM DEPOSIT"):
        return [row("DEPOSIT_TRANSFER_IN")]
    if narrative.startswith("TRANSFER FROM"):
        return [row("CASH_TRANSFER_IN", notes=narrative)]
    if narrative.startswith("BACS Payment"):
        # From the dividends ledger these are income paid out to the beneficiary; from the
        # capital ledger, a capital withdrawal. Both leave the trust.
        return [
            row(
                "INCOME_DISTRIBUTION" if ledger == "dividends" else "WITHDRAWAL",
                notes=narrative,
            )
        ]
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


def _entry_key(ledger: str, e: dict) -> tuple:
    return (ledger, e["date"], e["reference"], e["narrative"], e["debit"], e["credit"])


def combine(statements: list[dict]) -> tuple[list[dict], list[dict]]:
    """Merge statements into one row list per ledger, dropping duplicates across overlaps.

    Returns (rows, coverage). Raises if a statement's opening balance disagrees with the entries
    already seen for its ledger over a contiguous or overlapping period.
    """
    rows: list[dict] = []
    coverage: list[dict] = []
    by_ledger = collections.defaultdict(list)
    for s in statements:
        by_ledger[s["ledger"]].append(s)

    for ledger, group in by_ledger.items():
        group.sort(key=lambda s: (s["period_start"], s["period_end"]))
        seen: set[tuple] = set()
        ledger_rows: list[dict] = []
        covered_to: date | None = None
        for s in group:
            balance_before = round(
                sum(
                    r["amount_gbp"] or 0.0
                    for r in ledger_rows
                    if r["tx_date"] < s["period_start"].isoformat()
                ),
                2,
            )
            start_iso = s["period_start"].isoformat()
            if covered_to is None:
                ledger_rows.append(
                    _balance_row(
                        ledger,
                        start_iso,
                        "OPENING_BALANCE",
                        s["opening"],
                        "Ledger opening cash balance",
                    )
                )
            elif s["period_start"] <= covered_to + timedelta(days=1):
                if abs(balance_before - s["opening"]) > 0.005:
                    raise ValueError(
                        f"{s['source_file']} {ledger}: opening balance {s['opening']:,.2f} on {start_iso} "
                        f"does not match {balance_before:,.2f} from the earlier statements"
                    )
            else:
                gap = round(s["opening"] - balance_before, 2)
                ledger_rows.append(
                    _balance_row(
                        ledger,
                        start_iso,
                        "BALANCE_ADJUSTMENT",
                        gap,
                        f"Unseen net movement between {covered_to} and {start_iso} (no statement)",
                    )
                )
            for e in s["entries"]:
                key = _entry_key(ledger, e)
                if key in seen:
                    continue
                seen.add(key)
                ledger_rows.extend(classify(e, ledger))
            covered_to = max(covered_to or s["period_end"], s["period_end"])
            coverage.append(
                {
                    "ledger": ledger,
                    "period_start": start_iso,
                    "period_end": s["period_end"].isoformat(),
                    "opening_gbp": s["opening"],
                    "closing_gbp": s["closing"],
                    "source_file": s["source_file"],
                }
            )
        rows.extend(ledger_rows)

    order = {name: i for i, (_, name) in enumerate(reversed(LEDGER_HEADINGS))}
    rows.sort(
        key=lambda r: (
            order[r["ledger"]],
            r["tx_date"],
            r["tx_type"] not in ("OPENING_BALANCE", "BALANCE_ADJUSTMENT"),
        )
    )
    coverage.sort(key=lambda c: (order[c["ledger"]], c["period_start"]))
    return rows, coverage


def _balance_row(
    ledger: str, tx_date: str, tx_type: str, amount: float, notes: str
) -> dict:
    return {
        "ledger": ledger,
        "tx_date": tx_date,
        "reference": None,
        "tx_type": tx_type,
        "security": "",
        "quantity": None,
        "amount_gbp": amount,
        "notes": notes,
    }


def find_pdfs(inputs: list[str]) -> list[Path]:
    if inputs:
        paths: list[Path] = []
        for item in inputs:
            p = Path(item)
            paths.extend(sorted(p.rglob(PDF_GLOB)) if p.is_dir() else [p])
        return paths
    for d in DEFAULT_SEARCH_DIRS:
        found = sorted(d.rglob(PDF_GLOB)) if d.exists() else []
        if found:
            return found
    return []


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: ("" if r[k] is None else r[k]) for k in fields})


EXTERNAL_TYPES = ("CASH_TRANSFER_IN", "WITHDRAWAL", "INCOME_DISTRIBUTION")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("inputs", nargs="*", help="Ledger PDFs or folders to search")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv[1:])

    pdfs = find_pdfs(args.inputs)
    if not pdfs:
        looked = ", ".join(args.inputs) or ", ".join(
            str(d) for d in DEFAULT_SEARCH_DIRS
        )
        print(
            f"No ledger PDFs matching {PDF_GLOB!r} found (looked in: {looked})",
            file=sys.stderr,
        )
        return 1

    try:
        statements = [s for p in pdfs for s in read_statements(p)]
        rows, coverage = combine(statements)
    except ValueError as exc:
        print(f"{exc}. Nothing written.", file=sys.stderr)
        return 1

    write_csv(args.out_dir / "pelm_transactions.csv", FIELDS, rows)
    write_csv(args.out_dir / "pelm_ledger_coverage.csv", COVERAGE_FIELDS, coverage)

    print(f"Read {len(pdfs)} PDF(s), {len(statements)} statements, all reconciled:")
    for c in coverage:
        print(
            f"  {c['ledger']:9} {c['period_start']} to {c['period_end']}  "
            f"opening {c['opening_gbp']:>11,.2f}  closing {c['closing_gbp']:>11,.2f}  ({c['source_file']})"
        )
    print(f"Wrote {len(rows)} rows to {args.out_dir / 'pelm_transactions.csv'}")
    for tx_type, n in sorted(collections.Counter(r["tx_type"] for r in rows).items()):
        print(f"  {tx_type:22} {n}")
    for r in rows:
        if r["tx_type"] == "OTHER":
            print(
                f"  note: unclassified entry kept as OTHER: {r['ledger']} {r['tx_date']} {r['security']}"
            )
        if r["tx_type"] == "BALANCE_ADJUSTMENT":
            print(
                f"  note: {r['ledger']} gap before {r['tx_date']}: {r['amount_gbp']:,.2f} carried as BALANCE_ADJUSTMENT"
            )

    flows: dict[str, float] = collections.defaultdict(float)
    for r in rows:
        if r["tx_type"] in EXTERNAL_TYPES and r["amount_gbp"] is not None:
            flows[r["tx_date"][:7]] += r["amount_gbp"]
    print("External cash flows by month (dbt derives the PELM flows from these):")
    for month in sorted(flows):
        print(f"  {month}  {flows[month]:>12,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
