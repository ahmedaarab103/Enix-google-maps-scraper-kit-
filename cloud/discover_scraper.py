"""Cautious cloud importer for Enix's EXISTING Google Maps scraper.

Manual smoke test (no network and no credentials):
    python cloud/discover_scraper.py --mode dry-run --input cloud/fixtures/sample_businesses.csv

A LIVE scrape requires an explicit environment switch, a private Sheets service
account, the existing local scraper API running at 127.0.0.1:8080, and owner
review of Google's terms. This program never extracts or stores email addresses.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import gspread
from google.oauth2.service_account import Credentials

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("company", "city", "website", "industry", "country", "status",
          "approved", "notes", "source_url")
MAX_LEADS = 10
DEPTH = 2
MAX_TIME = 180
DEFAULT_CITY = "Marrakech Morocco"
DEFAULT_QUERY = "hotels and riads in Marrakech Morocco"
CONFIG_MARKER = "scraper_last_started_utc"


def _domain(url):
    value = (url or "").strip()
    if not value:
        return ""
    if not value.startswith(("https://", "http://")):
        value = "https://" + value
    p = urlparse(value)
    if p.scheme not in ("https", "http") or not p.hostname:
        return ""
    host = p.hostname.lower()
    return host.removeprefix("www.")


def normalized_records(csv_path, city=DEFAULT_CITY):
    with open(csv_path, newline="", encoding="utf-8-sig") as stream:
        source = csv.DictReader(stream)
        if not source.fieldnames or "title" not in source.fieldnames:
            raise ValueError("Expected the scraper CSV format containing a title column")
        seen = set()
        records = []
        for item in source:
            name = (item.get("title") or "").strip()
            website = (item.get("website") or "").strip()
            dom = _domain(website)
            if not name or not dom:
                continue
            company_key = (name.casefold(), city.casefold())
            if dom in seen or company_key in seen:
                continue
            seen.add(dom)
            seen.add(company_key)
            records.append({
                "company": name,
                "city": city,
                "website": website,
                "industry": (item.get("category") or "").strip(),
                "country": "Morocco",
                "status": "NEW",
                "approved": "NO",
                "notes": "Scraper discovery: independently verify this business before outreach.",
                "source_url": "",
            })
            if len(records) >= MAX_LEADS:
                break
        return records


def _open_book():
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    sid = os.getenv("GOOGLE_SHEET_ID", "")
    if not raw or not sid:
        raise RuntimeError("Private Google Sheet service account and ID are required.")
    creds = Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(creds).open_by_key(sid)


def _read_config(ws):
    vals = ws.get_all_values()
    return {str(r[0]).strip(): (i, str(r[1]).strip() if len(r) > 1 else "")
            for i, r in enumerate(vals[1:], start=2) if r and r[0]}


def _start_guard(book):
    """Prevent an automatic re-scrape within 24 hours by using CRM Config."""
    ws = book.worksheet("Config")
    config = _read_config(ws)
    if config.get("discovery_enabled", (None, "FALSE"))[1].upper() != "TRUE":
        raise RuntimeError("CRM Config discovery_enabled is FALSE; no scraping.")
    latest = config.get(CONFIG_MARKER, (None, ""))[1]
    if latest:
        try:
            past = datetime.fromisoformat(latest.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - past).total_seconds() < 86400:
                raise RuntimeError("Discovery was started in the last 24 hours; skipping.")
        except ValueError:
            raise RuntimeError("Invalid Config last-start timestamp. Manual review needed.")
    now = datetime.now(timezone.utc).isoformat()
    if CONFIG_MARKER in config:
        ws.update_cell(config[CONFIG_MARKER][0], 2, now)
    else:
        ws.append_row([CONFIG_MARKER, now, "24h no-retry guard for cautious scraper"])


def _import(book, records):
    if not records:
        return 0
    ws = book.worksheet("Leads")
    grid = ws.get_all_values()
    if not grid:
        raise RuntimeError("Leads sheet is missing its header")
    headers = [h.strip() for h in grid[0]]
    missing = set(FIELDS) - set(headers)
    if missing:
        raise RuntimeError("Leads sheet columns missing: " + ", ".join(sorted(missing)))
    current = [dict(zip(headers, row + [""] * max(0, len(headers)-len(row)))) for row in grid[1:]]
    sites = {_domain(r.get("website")) for r in current if _domain(r.get("website"))}
    names = {(r.get("company","").strip().casefold(),r.get("city","").strip().casefold()) for r in current}
    added = 0
    for rec in records:
        if _domain(rec["website"]) in sites or (rec["company"].casefold(),rec["city"].casefold()) in names:
            continue
        # No email addresses or phone numbers, and no approval is inferred.
        row = [rec.get(h, "") for h in headers]
        ws.append_row(row, value_input_option="RAW")
        sites.add(_domain(rec["website"]))
        names.add((rec["company"].casefold(),rec["city"].casefold()))
        added += 1
    return added


def _live_csv():
    """Use the existing API-backed Python scraper; never run multiple jobs."""
    if os.getenv("ENIX_DISCOVERY_ENABLED","").lower() != "true":
        raise RuntimeError("ENIX_DISCOVERY_ENABLED is not true; live scraper disabled.")
    base = os.getenv("SCRAPER_BASE_URL", "http://127.0.0.1:8080")
    if base not in ("http://127.0.0.1:8080", "http://localhost:8080"):
        raise RuntimeError("Scraper API must stay bound to localhost, never a public URL.")
    fd, output = tempfile.mkstemp(prefix="enix-discovery-", suffix=".csv")
    os.close(fd)
    cmd = [
        sys.executable, str(ROOT / "scripts" / "scrape.py"),
        DEFAULT_QUERY, "31.6295", "-7.9811",
        "--depth", str(DEPTH), "--max-time", str(MAX_TIME),
        "--no-email", "--fields", "title,website,category,address",
        "--out", output,
    ]
    try:
        proc = subprocess.run(cmd, check=False, capture_output=True, text=True,
                              timeout=MAX_TIME+90, cwd=ROOT)
        # Never expose contact information printed by the legacy script.
        if proc.returncode != 0:
            raise RuntimeError("Scraper failed; no automatic retry. Check the local private log.")
        return output
    except Exception:
        Path(output).unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("dry-run","import","live"), default="dry-run")
    parser.add_argument("--input", help="CSV export from existing scraper; required in dry-run/import")
    args = parser.parse_args()
    if args.mode in ("dry-run","import") and not args.input:
        parser.error("--input required for dry-run or import")
    if args.mode == "dry-run":
        found = normalized_records(args.input)
        print("OFFLINE SAFE MODE: would add at most",len(found),"business records.")
        print("No Google requests, no sheet writes, no emails.")
        return
    if args.mode == "import":
        records = normalized_records(args.input)
        # Owner explicitly supplied CSV; still requires private service-account access.
        print("Imported new business records:", _import(_open_book(),records))
        return
    book = _open_book()
    _start_guard(book)  # reserves the daily attempt BEFORE touching Google Maps
    output = _live_csv()
    try:
        records = normalized_records(output)
        print("New business records added:",_import(book,records))
    finally:
        Path(output).unlink(missing_ok=True)
    print("One small scrape finished. Email sending is unaffected and remains separate.")


if __name__ == "__main__":
    main()
