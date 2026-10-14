"""Safe offline tests for ENIX cloud automation; all network services are mocked."""
import io
import json
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import outreach
import discover

HEADERS = "company,industry,city,country,website,email,source_url,contact_name,language,pain_point,offer,subject,body,status,approved,first_sent_utc,last_sent_utc,followup_count,last_reply_utc,next_action_utc,last_message_id,last_error,notes".split(",")
ACTIVITY = ["timestamp_utc","email","company","event","details","message_id"]
SUPPRESSION = ["email","reason","added_utc","source"]
CONFIG = ["key","value","description"]

class FakeWS:
    def __init__(self, headers, records=None):
        self.headers = headers
        self.records = [dict(r) for r in (records or [])]
    def get_all_values(self):
        return [self.headers] + [[str(r.get(k,"")) for k in self.headers] for r in self.records]
    def update_cell(self, row, col, value):
        self.records[row-2][self.headers[col-1]] = str(value)
    def append_row(self, row, value_input_option=None):
        self.records.append(dict(zip(self.headers, [str(x) for x in row])))

class FakeBook:
    def __init__(self, leads=None, suppression=None, history=None, enabled="FALSE"):
        self.tabs = {
            "Leads": FakeWS(HEADERS, leads),
            "Suppression": FakeWS(SUPPRESSION, suppression),
            "Activity": FakeWS(ACTIVITY, history),
            "Config": FakeWS(CONFIG, [{"key":"outbound_enabled","value":enabled}]),
        }
    def worksheet(self,name):
        return self.tabs[name]

class FakeSMTP:
    sent = []
    def __init__(self,*args,**kwargs): pass
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def login(self,*args): pass
    def send_message(self,msg):
        self.sent.append(msg)

def lead(email_addr="client@example.org",**kwargs):
    r={"company":"Example Company","email":email_addr,"status":"READY","approved":"YES",
       "subject":"Bonjour","body":"Je vous contacte pour un projet photo.","followup_count":"0"}
    r.update(kwargs)
    return r

class OutreachSafetyTests(unittest.TestCase):
    def setUp(self):
        FakeSMTP.sent.clear()
        outreach.NOW=datetime(2026,10,14,11,0,tzinfo=timezone.utc)
        outreach.SENDER="contact@enix.ma"
        self.env=patch.dict(os.environ,{"IMAP_HOST":"mock.imap","SMTP_USER":"contact@enix.ma",
            "SMTP_PASS":"fake","SMTP_HOST":"mock.smtp","SMTP_PORT":"465"},clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.smtp=patch.object(outreach.smtplib,"SMTP_SSL",FakeSMTP)
        self.smtp.start()
        self.addCleanup(self.smtp.stop)
        self.replies=patch.object(outreach,"check_reply_addresses",return_value=set())
        self.replies.start()
        self.addCleanup(self.replies.stop)
    def run_book(self,book,active):
        with patch.object(outreach,"sheet",return_value=book):
            with patch.object(outreach,"ACTIVE",active):
                outreach.main()
        return book
    def test_dry_run_never_sends(self):
        b=self.run_book(FakeBook([lead()],enabled="TRUE"),False)
        self.assertEqual(len(FakeSMTP.sent),0)
        self.assertEqual(len(b.tabs["Activity"].records),0)
    def test_private_crm_switch_blocks_even_when_actions_enabled(self):
        self.run_book(FakeBook([lead()],enabled="FALSE"),True)
        self.assertEqual(len(FakeSMTP.sent),0)
    def test_only_approved_and_deduplicated(self):
        b=FakeBook([lead(),lead("client@example.org",company="Duplicate"),
            lead("unapproved@example.org",approved="NO")],enabled="TRUE")
        self.run_book(b,True)
        self.assertEqual(len(FakeSMTP.sent),1)
        self.assertEqual(len(b.tabs["Activity"].records),2)
        self.assertEqual({x["event"] for x in b.tabs["Activity"].records},{"RESERVED","SENT"})
    def test_suppressed_and_reply_excluded(self):
        b=FakeBook([lead("blocked@example.org"),lead("replied@example.org")],
            suppression=[{"email":"blocked@example.org"}],enabled="TRUE")
        with patch.object(outreach,"check_reply_addresses",return_value={"replied@example.org"}):
            self.run_book(b,True)
        self.assertEqual(len(FakeSMTP.sent),0)
        self.assertEqual(b.tabs["Leads"].records[1]["status"],"REPLIED")
    def test_reserved_without_terminal_result_not_retried(self):
        history=[{"timestamp_utc":"2026-10-13T10:00:00+00:00",
            "email":"client@example.org","event":"RESERVED","message_id":"<unknown@example.org>"}]
        self.run_book(FakeBook([lead()],history=history,enabled="TRUE"),True)
        self.assertEqual(len(FakeSMTP.sent),0)
    def test_daily_sent_and_reserved_count_once(self):
        history=[]
        for n in range(5):
            mid=f"<{n}@example.org>"
            for event in ("RESERVED","SENT"):
                history.append({"timestamp_utc":"2026-10-14T10:00:00+00:00",
                    "email":f"old{n}@example.org","event":event,"message_id":mid})
        b=FakeBook([lead()],history=history,enabled="TRUE")
        self.run_book(b,True)
        self.assertEqual(len(FakeSMTP.sent),1)
    def test_replies_prevent_followups(self):
        b=FakeBook([lead(status="SENT",last_sent_utc="2026-10-01T00:00:00+00:00")],enabled="TRUE")
        with patch.object(outreach,"check_reply_addresses",return_value={"client@example.org"}):
            self.run_book(b,True)
        self.assertEqual(len(FakeSMTP.sent),0)
        self.assertEqual(b.tabs["Leads"].records[0]["status"],"REPLIED")
    def test_followup_only_after_three_days_and_limit_two(self):
        b=FakeBook([
            lead("tooearly@example.org",status="SENT",last_sent_utc="2026-10-13T00:00:00+00:00"),
            lead("due@example.org",status="SENT",last_sent_utc="2026-10-10T00:00:00+00:00"),
            lead("done@example.org",status="SENT",followup_count="2",last_sent_utc="2026-10-01T00:00:00+00:00")
        ],enabled="TRUE")
        self.run_book(b,True)
        self.assertEqual(len(FakeSMTP.sent),1)
        self.assertEqual(FakeSMTP.sent[0]["To"],"due@example.org")
        self.assertEqual(b.tabs["Leads"].records[1]["followup_count"],"1")
        self.assertEqual(b.tabs["Activity"].records[-1]["event"],"FOLLOWUP_1")
        self.run_book(b,True)
        self.assertEqual(len(FakeSMTP.sent),1)
    def test_pending_followup_reservation_blocks_retry(self):
        history=[{"timestamp_utc":"2026-10-13T10:00:00+00:00",
            "email":"client@example.org","event":"RESERVED",
            "details":"FOLLOWUP","message_id":"<interrupted@example.org>"}]
        b=FakeBook([lead(status="SENT",last_sent_utc="2026-10-01T00:00:00+00:00")],
            history=history,enabled="TRUE")
        self.run_book(b,True)
        self.assertEqual(len(FakeSMTP.sent),0)
    def test_invalid_email_never_sent(self):
        b=FakeBook([lead("bad@"),lead("client\n@example.org")],enabled="TRUE")
        self.run_book(b,True)
        self.assertEqual(len(FakeSMTP.sent),0)

class DiscoverySafetyTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{},clear=True);self.env.start();self.addCleanup(self.env.stop)
    def test_default_disabled_does_not_call_places(self):
        with patch.object(discover.urllib.request,"urlopen") as req:
            discover.main()
            req.assert_not_called()
    def test_missing_key_fails_closed(self):
        with patch.dict(os.environ,{"ENIX_DISCOVERY_ENABLED":"true"},clear=True):
            with self.assertRaises(RuntimeError):
                discover.main()
    def test_verified_mock_places_are_added_once_no_email(self):
        b=FakeBook()
        response={"places":[
          {"id":"id-1","displayName":{"text":"Riad Sample"},"websiteUri":"https://riad.example","formattedAddress":"Marrakech"},
          {"id":"id-2","displayName":{"text":"Riad Sample"},"websiteUri":"https://riad.example","formattedAddress":"Marrakech"}]}
        def urlopen(req,timeout=0):
            return io.BytesIO(json.dumps(response).encode())
        with patch.dict(os.environ,{"ENIX_DISCOVERY_ENABLED":"true",
                   "GOOGLE_PLACES_API_KEY":"fake","GOOGLE_SERVICE_ACCOUNT_JSON":"{}",
                   "GOOGLE_SHEET_ID":"fake","ENIX_DISCOVERY_QUERY":"riads in Marrakech"}):
            with patch.object(discover.urllib.request,"urlopen",side_effect=urlopen):
                with patch.object(discover.Credentials,"from_service_account_info",return_value=object()):
                    with patch.object(discover.gspread,"authorize",return_value=MagicMock(open_by_key=lambda _:b)):
                        discover.main()
        self.assertEqual(len(b.tabs["Leads"].records),1)
        self.assertEqual(b.tabs["Leads"].records[0]["approved"],"NO")
        self.assertEqual(b.tabs["Leads"].records[0].get("email",""),"")

if __name__=="__main__":
    unittest.main()
