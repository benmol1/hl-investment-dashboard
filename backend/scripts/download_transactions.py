"""
Download HL transaction CSVs for ISA and SIPP using Playwright.

Persists browser session state to avoid re-authenticating on every run.
On first run from a new browser (or after session expiry), a full login is
performed. If HL prompts for an SMS OTP, the script exits with instructions —
re-run with HL_OTP=<code> to complete the first-time login. After that the
saved session should be trusted by HL and OTP won't be requested again.

How to find your account IDs:
  Log in to hl.co.uk, go to your ISA/SIPP, click "Transaction history",
  then export to CSV. The URL will contain /account/XXXXXX/ — that number is
  your account ID.

Required env vars:
    HL_USERNAME          HL client number (on your statements)
    HL_PASSWORD          Full HL password
    HL_SECURE_NUMBER     Full HL secure number (6-digit PIN)
    HL_ISA_ACCOUNT_ID    Numeric account ID for ISA
    HL_SIPP_ACCOUNT_ID   Numeric account ID for SIPP

Optional:
    HL_OTP               SMS one-time password — only needed on the very first
                         run when HL doesn't yet trust this browser session
    HL_SESSION_PATH      Where to persist session state
                         (default: <data_dir>/hl_session.json)
    HL_LOOKBACK_DAYS     Days of history to fetch per run (default: 90)
                         The ingestion script deduplicates, so overlapping
                         runs are harmless.
"""

import asyncio
import logging
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import requests as req_lib
from playwright.async_api import Page, async_playwright

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"
_IMPORT_BASE = _DATA_DIR / "imports" / "raw_transactions"
_HL_BASE = "https://online.hl.co.uk"


def _session_path() -> Path:
    default = _DATA_DIR / "hl_session.json"
    return Path(os.environ.get("HL_SESSION_PATH", default))


def _lookback_days() -> int:
    return int(os.environ.get("HL_LOOKBACK_DAYS", "90"))


def _require(name: str) -> str:
    val = os.environ.get(name, "").strip()
    if not val:
        raise SystemExit(f"Required env var {name!r} is not set")
    return val


def _parse_positions(label_text: str) -> list[int]:
    """
    Parse the character/digit position from an HL login label.
    Handles ordinal forms ("1st", "3rd") and bare numbers.
    Returns a list of 1-based integers.
    """
    nums = re.findall(r"\b(\d+)(?:st|nd|rd|th)?\b", label_text, re.IGNORECASE)
    return [int(n) for n in nums if 1 <= int(n) <= 20]


async def _fill_partial_inputs(page: Page, full_value: str) -> bool:
    """
    Fill the partial-entry character/digit inputs on an HL login page.

    HL presents N single-character inputs, each paired with a label that
    names the position (e.g. "3rd character of your password"). We parse the
    position from the label and fill the corresponding character.

    Returns True if at least one input was filled.
    """
    # Cast a wide net for single-char inputs — HL's exact class names may change
    inputs = await page.locator(
        "input[maxlength='1'], input[type='password'][maxlength='1'], "
        "input[name*='letter'], input[name*='digit'], input[name*='character']"
    ).all()

    if not inputs:
        return False

    filled = 0
    for inp in inputs:
        # Try to get the label: check aria-label, then look for a nearby <label>
        label_text = await inp.get_attribute("aria-label") or ""
        if not label_text:
            inp_id = await inp.get_attribute("id") or ""
            inp_name = await inp.get_attribute("name") or ""
            if inp_id:
                lbl = page.locator(f"label[for='{inp_id}']")
                if await lbl.count():
                    label_text = await lbl.first.inner_text()
            if not label_text and inp_name:
                # Name often encodes the position, e.g. "online-password-letter-3"
                label_text = inp_name

        positions = _parse_positions(label_text)
        if not positions:
            logger.warning("Could not determine position from label %r — skipping input", label_text)
            continue

        pos = positions[0]
        if pos > len(full_value):
            logger.error("Position %d exceeds value length %d", pos, len(full_value))
            continue

        char = full_value[pos - 1]
        await inp.fill(char)
        logger.debug("Filled position %d", pos)
        filled += 1

    return filled > 0


async def _is_logged_in(page: Page) -> bool:
    await page.goto(f"{_HL_BASE}/my-accounts/portfolio_overview", wait_until="domcontentloaded")
    return "login" not in page.url.lower()


async def _login(page: Page) -> bool:
    """
    Work through the HL multi-step login. Returns True on success.
    Exits (or returns False) if an unexpected page is encountered.
    """
    username = _require("HL_USERNAME")
    password = _require("HL_PASSWORD")
    secure_number = _require("HL_SECURE_NUMBER")
    otp = os.environ.get("HL_OTP", "").strip()

    logger.info("Starting HL login")
    await page.goto(f"{_HL_BASE}/my-accounts/login-step-one", wait_until="domcontentloaded")

    # Step 1: username
    username_field = page.locator("input#username, input[name='username']")
    if not await username_field.count():
        logger.error("Username field not found — HL page structure may have changed")
        return False
    await username_field.first.fill(username)
    await page.locator("button[type='submit'], input[type='submit']").first.click()
    await page.wait_for_load_state("domcontentloaded")
    logger.info("Username submitted; now at: %s", page.url)

    # Step 2: partial password
    if await _fill_partial_inputs(page, password):
        await page.locator("button[type='submit'], input[type='submit']").first.click()
        await page.wait_for_load_state("domcontentloaded")
        logger.info("Password step done; now at: %s", page.url)

    # Step 3: partial secure number
    if await _fill_partial_inputs(page, secure_number):
        await page.locator("button[type='submit'], input[type='submit']").first.click()
        await page.wait_for_load_state("domcontentloaded")
        logger.info("Secure number step done; now at: %s", page.url)

    # Step 4: SMS OTP — should not appear for trusted sessions; handle gracefully
    otp_field = page.locator(
        "input[name*='security-code'], input[name*='otp'], input[name*='one-time']"
    )
    if await otp_field.count():
        if not otp:
            logger.error(
                "\n"
                "HL is requesting an SMS one-time password and HL_OTP is not set.\n"
                "This only happens on the first login from a new browser session.\n"
                "Steps to fix:\n"
                "  1. Check your phone for the HL SMS code.\n"
                "  2. Re-run: HL_OTP=<code> python backend/scripts/download_transactions.py\n"
                "  3. After this succeeds, the session will be saved and OTP won't be\n"
                "     required on future automated runs.\n"
            )
            return False
        await otp_field.first.fill(otp)
        await page.locator("button[type='submit'], input[type='submit']").first.click()
        await page.wait_for_load_state("domcontentloaded")
        logger.info("OTP submitted; now at: %s", page.url)

    if "login" in page.url.lower():
        logger.error("Still on a login page after all steps — credentials may be wrong, or the page structure has changed")
        return False

    logger.info("Login successful")
    return True


def _download_csv(http_session: req_lib.Session, account_type: str, account_id: str) -> None:
    end_date = date.today()
    start_date = end_date - timedelta(days=_lookback_days())

    url = (
        f"{_HL_BASE}/my-accounts/investment_history_csv"
        f"/account/{account_id}"
        f"/view/CB/page/1/func/download"
        f"/startDate/{start_date.strftime('%Y-%m-%d')}"
        f"/endDate/{end_date.strftime('%Y-%m-%d')}"
    )

    logger.info("Downloading %s CSV (%s → %s)", account_type, start_date, end_date)
    response = http_session.get(url, timeout=30)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        raise RuntimeError(
            f"Got HTML instead of CSV for {account_type} — "
            "session may have expired or the account ID is wrong.\n"
            f"URL tried: {url}"
        )

    out_dir = _IMPORT_BASE / account_type
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{account_type}_{end_date.strftime('%Y-%m-%d')}.csv"
    out_path.write_bytes(response.content)
    logger.info("Saved %s CSV → %s (%d bytes)", account_type, out_path, len(response.content))


async def _run() -> None:
    isa_id = _require("HL_ISA_ACCOUNT_ID")
    sipp_id = _require("HL_SIPP_ACCOUNT_ID")
    session_file = _session_path()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )

        storage_state = str(session_file) if session_file.exists() else None
        context = await browser.new_context(
            storage_state=storage_state,
            # Use a realistic user-agent so HL doesn't reject the headless browser
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        logged_in = False
        if storage_state:
            logger.info("Checking saved session at %s", session_file)
            logged_in = await _is_logged_in(page)
            if logged_in:
                logger.info("Session still valid — skipping login")
            else:
                logger.info("Session expired — logging in")

        if not logged_in:
            if not await _login(page):
                await browser.close()
                sys.exit(1)
            await context.storage_state(path=str(session_file))
            logger.info("Session saved to %s", session_file)

        cookies = await context.cookies()
        await browser.close()

    http_session = req_lib.Session()
    for c in cookies:
        http_session.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))

    for account_type, account_id in [("ISA", isa_id), ("SIPP", sipp_id)]:
        _download_csv(http_session, account_type, account_id)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(_run())
