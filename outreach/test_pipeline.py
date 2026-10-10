import csv
import tempfile
import unittest
from pathlib import Path

from pipeline import open_db, import_csv, approve, export_csv, suppress, mark, report, import_history

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = open_db(self.root / "test.db")
    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()
    def csv_file(self, name, rows, headers=("title","emails","website","city")):
        p=self.root/name
        with p.open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=headers);w.writeheader();w.writerows(rows)
        return p
    def test_company_and_email_unique_across_brands(self):
        a=self.csv_file("a.csv",[
            {"title":"Hotel A","emails":"INFO@hotela.test","website":"https://hotela.test","city":"Casablanca"},
            {"title":"Hotel A second","emails":"sales@hotela.test","website":"https://www.hotela.test","city":"Casablanca"},
        ])
        self.assertEqual(import_csv(self.db,a,"ENIX")["added"],1)
        b=self.csv_file("b.csv",[{"title":"Other brand","emails":"INFO@hotela.test","website":"hotelb.test","city":"Rabat"}])
        self.assertEqual(import_csv(self.db,b,"WENIX")["duplicates"],1)
        self.assertEqual(self.db.execute("SELECT count(*) FROM leads").fetchone()[0],1)
    def test_no_export_before_approval_and_no_duplicate_exports(self):
        path=self.csv_file("new.csv",[{"title":"Cafe","emails":"hello@cafe.test","website":"cafe.test","city":"Agadir"}])
        import_csv(self.db,path,"WENIX")
        output=self.root/"out.csv"
        with self.assertRaises(ValueError): export_csv(self.db,"WENIX",output,8)
        self.assertEqual(export_csv(self.db,"WENIX",output,8,True),0)
        approve(self.db,1,"Individually verified company contact; approved for relevant B2B outreach")
        self.assertEqual(export_csv(self.db,"WENIX",output,8,True),1)
        self.assertEqual(export_csv(self.db,"WENIX",output,8,True),0)
        self.assertEqual(mark(self.db,"hello@cafe.test","sent","provider-msg-123"),"sent")
        self.assertEqual(report(self.db)[0]["status"],"sent")
    def test_suppression_and_bounce(self):
        path=self.csv_file("supp.csv",[
            {"title":"Agency A","emails":"hi@agency-a.test","website":"agency-a.test","city":"Rabat"},
            {"title":"Agency B","emails":"hi@agency-b.test","website":"agency-b.test","city":"Rabat"}
        ])
        self.assertEqual(import_csv(self.db,path,"ENIX")["added"],2)
        approve(self.db,1,"Verified B2B business address with documented relevance")
        approve(self.db,2,"Verified B2B business address with documented relevance")
        suppress(self.db,"company","agency-a.test","Manual exclusion")
        self.assertEqual(export_csv(self.db,"ENIX",self.root/"out.csv",8,True),1)
        self.assertEqual(mark(self.db,"hi@agency-b.test","bounced"),"bounced")
        self.assertEqual(export_csv(self.db,"ENIX",self.root/"out2.csv",8,True),0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM suppressions").fetchone()[0],2)
    def test_previously_contacted_is_suppressed(self):
        old=self.csv_file("history.csv",[{"to":"sent@test.test"}],("to",))
        self.assertEqual(import_history(self.db,old),1)
        leads=self.csv_file("leads.csv",[{"title":"Sent Co","emails":"sent@test.test","website":"sent-co.test","city":"Fes"}])
        self.assertEqual(import_csv(self.db,leads,"ENIX")["skipped"],1)

if __name__ == "__main__":
    unittest.main()
