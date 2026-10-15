"""Offline evidence-based event urgency tests. No API, no emails."""
import unittest
from datetime import date, timedelta
from event_priority import prioritize, classify_row
from score_event_leads import refresh_priorities
from test_scraper import FakeBook

TODAY=date(2026,10,15)
EVENT_URL="https://events.example.org/conference-2026"
BRIEF_URL="https://events.example.org/supplier-tender"

class EventUrgencyTests(unittest.TestCase):
    def when(self,days, need="UNKNOWN", need_source=""):
        return prioritize((TODAY+timedelta(days=days)).isoformat(),EVENT_URL,
                          need,need_source,today=TODAY)
    def test_no_verified_event_is_research(self):
        self.assertEqual(prioritize("2026-10-22","",today=TODAY)[0],"RESEARCH")
        self.assertEqual(prioritize("",EVENT_URL,today=TODAY)[0],"RESEARCH")
    def test_verified_open_brief_under_three_weeks_is_p1(self):
        value,why=self.when(12,"OPEN_BRIEF",BRIEF_URL)
        self.assertEqual(value,"P1")
        self.assertIn("Published",why)
    def test_unverified_need_is_never_p1(self):
        self.assertEqual(self.when(10,"OPEN_BRIEF","")[0],"P2")
        self.assertEqual(self.when(10)[0],"P2")
    def test_midrange_event_is_p3(self):
        self.assertEqual(self.when(60)[0],"P3")
    def test_old_event_expires(self):
        self.assertEqual(self.when(-1)[0],"EXPIRED")
    def test_far_future_not_rushed(self):
        self.assertEqual(self.when(120)[0],"FUTURE")
    def test_date_without_source_is_unverified(self):
        self.assertEqual(prioritize("2026-11-01","ftp://events.example",today=TODAY)[0],"RESEARCH")
    def test_score_sheet_dry_run_does_not_write(self):
        ds=(date.today()+timedelta(days=10)).isoformat()
        b=FakeBook(saved=[{"company":"Conference Team","city":"Marrakech Morocco","event_title":"Conference 2026",
            "event_date":ds,"event_source_url":EVENT_URL,
            "coverage_need":"UNKNOWN","priority":"RESEARCH"}])
        out=refresh_priorities(b,apply=False)
        self.assertEqual(out["priority_updates"],1)
        self.assertEqual(b.tabs["Leads"].records[0]["priority"],"RESEARCH")
    def test_explicit_apply_updates_only_priority(self):
        ds=(date.today()+timedelta(days=9)).isoformat()
        b=FakeBook(saved=[{"company":"Event Organizers","city":"Marrakech Morocco","event_title":"Summit 2026",
            "event_date":ds,"event_source_url":EVENT_URL,
            "coverage_need":"OPEN_BRIEF","coverage_need_source_url":BRIEF_URL,
            "priority":"RESEARCH","approved":"NO"}])
        out=refresh_priorities(b,apply=True)
        self.assertEqual(out["priority_updates"],1)
        self.assertEqual(b.tabs["Leads"].records[0]["priority"],"P1")
        self.assertEqual(b.tabs["Leads"].records[0]["approved"],"NO")
    def test_named_event_is_required_for_urgency(self):
        row={"event_date":"2026-10-22","event_source_url":EVENT_URL,
             "coverage_need":"OPEN_BRIEF","coverage_need_source_url":BRIEF_URL}
        self.assertEqual(classify_row(row,today=TODAY)[0],"RESEARCH")

    def test_scraped_organizer_has_no_invented_event_date(self):
        from discover_scraper import normalized_records
        from pathlib import Path
        fixture=Path(__file__).with_name("fixtures")/"sample_businesses.csv"
        records=normalized_records(fixture)
        self.assertTrue(all(r["event_date"]=="" and r["priority"]=="RESEARCH" 
                            and r["coverage_need"]=="UNKNOWN" for r in records))

if __name__=="__main__":
    unittest.main()
