"""Offline tests: no Google Maps requests, no billing, no real emails."""
import csv
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import discover_scraper as worker


class FakeSheet:
    def __init__(self, headers, records=None):
        self.headers = headers
        self.records = [dict(x) for x in (records or [])]
    def get_all_values(self):
        return [self.headers] + [[str(x.get(h,"")) for h in self.headers] for x in self.records]
    def append_row(self, values, value_input_option=None):
        self.records.append(dict(zip(self.headers, values)))
    def update_cell(self, row, col, value):
        self.records[row-2][self.headers[col-1]] = str(value)


class FakeBook:
    def __init__(self, enabled="TRUE", saved=None):
        self.tabs = {
            "Leads": FakeSheet(list(worker.FIELDS)+["email"],saved),
            "Config": FakeSheet(["key","value","description"],
                               [{"key":"discovery_enabled","value":enabled}])
        }
    def worksheet(self, name):
        return self.tabs[name]


class ScraperSafetyTests(unittest.TestCase):
    def setUp(self):
        self.file = Path(__file__).with_name("fixtures") / "sample_businesses.csv"

    def test_offline_source_dedupe_skips_private_emails(self):
        entries = worker.normalized_records(self.file)
        self.assertEqual(len(entries),2)
        self.assertTrue(all(x["approved"]=="NO" and x["status"]=="NEW" for x in entries))
        self.assertTrue(all("email" not in x and "phone" not in x for x in entries))

    def test_import_is_idempotent_and_never_approves(self):
        b = FakeBook()
        entries = worker.normalized_records(self.file)
        self.assertEqual(worker._import(b,entries),2)
        self.assertEqual(worker._import(b,entries),0)
        self.assertEqual(len(b.tabs["Leads"].records),2)
        self.assertTrue(all(x["email"]=="" and x["approved"]=="NO" for x in b.tabs["Leads"].records))

    def test_existing_domain_and_company_city_dedupe(self):
        entries = worker.normalized_records(self.file)
        b = FakeBook(saved=[{"company":"Another business","city":"Marrakech Morocco",
                             "website":"https://www.atlas-riad.example"}])
        self.assertEqual(worker._import(b,entries),1)

    def test_disabled_config_prevents_scrape(self):
        b = FakeBook(enabled="FALSE")
        with self.assertRaisesRegex(RuntimeError,"FALSE"):
            worker._start_guard(b)
        self.assertNotIn(worker.CONFIG_MARKER, str(b.tabs["Config"].records))

    def test_previous_attempt_prevents_retry(self):
        b = FakeBook()
        worker._start_guard(b)
        with self.assertRaisesRegex(RuntimeError,"24 hours"):
            worker._start_guard(b)
        self.assertEqual(len(b.tabs["Config"].records),2)

    def test_live_disabled_prevents_access(self):
        with patch.dict(os.environ,{"ENIX_DISCOVERY_ENABLED":"false"}):
            with patch.object(worker,"_open_book",side_effect=AssertionError("Should not access Sheets")):
                with patch.object(worker,"_live_csv",side_effect=AssertionError("Should not scrape")):
                    with patch("sys.argv",["discover_scraper.py","--mode","live"]):
                        with self.assertRaisesRegex(RuntimeError,"disabled"):
                            worker.main()

    def test_non_local_scraper_url_rejected(self):
        with patch.dict(os.environ,{"ENIX_DISCOVERY_ENABLED":"true",
                                  "SCRAPER_BASE_URL":"https://outside.example"}):
            with self.assertRaisesRegex(RuntimeError,"localhost"):
                worker._live_csv()

    def test_offline_dryrun_requires_no_network(self):
        with patch.object(worker,"_open_book",side_effect=AssertionError("unexpected Sheets call")):
            with patch.object(worker,"_live_csv",side_effect=AssertionError("unexpected scraper call")):
                with patch("sys.argv",["discover_scraper.py","--mode","dry-run",
                                       "--input",str(self.file)]):
                    worker.main()

if __name__=="__main__":
    unittest.main()
