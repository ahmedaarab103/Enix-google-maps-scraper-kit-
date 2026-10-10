#!/usr/bin/env python3
"""Offline safety gate for dual-brand outreach. Does not send email or scrape sites."""
import argparse
import csv
from datetime import datetime, timezone
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
BRANDS = ("ENIX", "WENIX")
TERMINAL = {"sent", "replied", "bounced", "opted_out"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  company TEXT NOT NULL,
  company_key TEXT NOT NULL UNIQUE,
  brand TEXT NOT NULL CHECK (brand IN ('ENIX','WENIX')),
  website TEXT NOT NULL DEFAULT '',
  city TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'new',
  legal_basis TEXT NOT NULL DEFAULT '',
  approved_at TEXT,
  reserved_at TEXT,
  provider_message_id TEXT UNIQUE,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS suppressions (
  kind TEXT NOT NULL CHECK(kind IN ('email','company')),
  value TEXT NOT NULL,
  reason TEXT NOT NULL,
  added_at TEXT NOT NULL,
  PRIMARY KEY(kind,value)
);
CREATE INDEX IF NOT EXISTS lead_brand_status ON leads(brand,status);
"""

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def open_db(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db

def email_from(value):
    match = EMAIL.search(str(value or ""))
    return match.group(0).lower() if match else ""

def company_key(name="", website=""):
    url = str(website or "").strip()
    if url:
        host = urlsplit(url if "://" in url else "https://" + url).hostname or ""
        host = host.lower().strip(".")
        if host.startswith("www."):
            host = host[4:]
        if host and "." in host:
            return "domain:" + host
    label = re.sub(r"\W+", " ", str(name).lower(), flags=re.UNICODE).strip()
    return "name:" + label if label else ""

def is_suppressed(db, email, key):
    return bool(db.execute("SELECT 1 FROM suppressions WHERE (kind='email' AND value=?) OR (kind='company' AND value=?)",
                           (email, key)).fetchone())

def import_csv(db, filename, brand, source="csv"):
    added = duplicate = skipped = 0
    with open(filename, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            email = email_from(row.get("emails") or row.get("email") or row.get("Email"))
            company = str(row.get("title") or row.get("name") or row.get("company") or "").strip()
            website = str(row.get("website") or row.get("Website") or "").strip()
            key = company_key(company, website)
            if not email or not company or not key or is_suppressed(db, email, key):
                skipped += 1
                continue
            try:
                db.execute("""INSERT INTO leads
                 (email,company,company_key,brand,website,city,category,source,status,updated_at)
                 VALUES(?,?,?,?,?,?,?,?, 'new',?)""",
                 (email, company, key, brand, website,
                  str(row.get("city") or row.get("address") or ""),
                  str(row.get("category") or ""), source, now()))
                added += 1
            except sqlite3.IntegrityError:
                duplicate += 1
    db.commit()
    return {"added": added, "duplicates": duplicate, "skipped": skipped}

def approve(db, lead_id, basis):
    if len(basis.strip()) < 12:
        raise ValueError("Specify the documented lawful basis and verification, not a generic approval.")
    row = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    if not row:
        raise ValueError("Unknown lead")
    if row["status"] != "new" or is_suppressed(db, row["email"], row["company_key"]):
        raise ValueError("Lead is not eligible for approval")
    db.execute("UPDATE leads SET status='approved',legal_basis=?,approved_at=?,updated_at=? WHERE id=?",
               (basis.strip(), now(), now(), lead_id))
    db.commit()

def suppress(db, kind, value, reason):
    if kind == "email":
        key = email_from(value)
    else:
        key = value if value.startswith(("domain:", "name:")) else company_key(value, value if "." in value else "")
    if not key:
        raise ValueError("Invalid suppression key")
    db.execute("INSERT OR REPLACE INTO suppressions(kind,value,reason,added_at) VALUES(?,?,?,?)",
               (kind,key,reason,now()))
    column = "email" if kind == "email" else "company_key"
    db.execute(f"UPDATE leads SET status='opted_out',updated_at=? WHERE {column}=? AND status NOT IN ('sent','replied','bounced')",
               (now(),key))
    db.commit()
    return key

def export_csv(db, brand, filename, limit, confirmed=False):
    if not confirmed:
        raise ValueError("Export is locked until --confirmed: review legal basis, suppression and provider policy.")
    if limit < 1 or limit > 25:
        raise ValueError("Use a conservative export limit between 1 and 25")
    db.execute("BEGIN IMMEDIATE")
    date = now()[:10]
    exported = db.execute("SELECT count(*) FROM leads WHERE brand=? AND substr(reserved_at,1,10)=?",
                          (brand, date)).fetchone()[0]
    available = max(0, min(limit, 10 - exported))  # default max 10 per brand per UTC day
    rows = db.execute("""SELECT * FROM leads
         WHERE brand=? AND status='approved' AND approved_at IS NOT NULL
         ORDER BY approved_at,id""", (brand,)).fetchall()
    eligible = [r for r in rows if not is_suppressed(db,r["email"],r["company_key"])][:available]
    fields = ["email","company","website","city","category","brand","legal_basis"]
    target=Path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp=target.with_suffix(target.suffix+".tmp")
    try:
        with open(temp,"w",newline="",encoding="utf-8") as fh:
            writer=csv.DictWriter(fh,fieldnames=fields)
            writer.writeheader()
            for r in eligible:
                writer.writerow({f:r[f] for f in fields})
        for r in eligible:
            db.execute("UPDATE leads SET status='reserved',reserved_at=?,updated_at=? WHERE id=? AND status='approved'",
                       (now(),now(),r["id"]))
        temp.replace(target)
        db.commit()
    except Exception:
        db.rollback()
        temp.unlink(missing_ok=True)
        raise
    return len(eligible)

def mark(db, email, status, provider_id=""):
    if status not in ("sent","replied","bounced","opted_out","release"):
        raise ValueError("Unsupported status")
    address = email_from(email)
    row = db.execute("SELECT * FROM leads WHERE email=?", (address,)).fetchone()
    if not row:
        if status in ("sent","replied","bounced","opted_out"):
            suppress(db,"email",address,"Historical contact or bounce")
            return "suppressed unknown historical address"
        raise ValueError("Unknown email")
    if status == "release":
        if row["status"] != "reserved":
            raise ValueError("Only an unsent reservation may be released after checking sender logs.")
        db.execute("UPDATE leads SET status='approved',reserved_at=NULL,updated_at=? WHERE id=?", (now(),row["id"]))
    elif status == "sent":
        if row["status"] != "reserved" or not provider_id:
            raise ValueError("Sent requires a prior reservation and provider message ID")
        db.execute("UPDATE leads SET status='sent',provider_message_id=?,updated_at=? WHERE id=?",
                   (provider_id,now(),row["id"]))
    else:
        db.execute("UPDATE leads SET status=?,updated_at=? WHERE id=?", (status,now(),row["id"]))
        if status in ("bounced","opted_out"):
            suppress(db,"email",address,status)
            return status
    db.commit()
    return status

def import_history(db, filename):
    processed=0
    with open(filename,newline="",encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            addr = email_from(row.get("to") or row.get("email") or row.get("recipient"))
            if addr:
                suppress(db,"email",addr,"Previously contacted; imported history")
                processed += 1
    return processed

def report(db):
    summary = db.execute("SELECT brand,status,count(*) n FROM leads GROUP BY brand,status ORDER BY brand,status").fetchall()
    return [dict(row) for row in summary]

def main():
    parser=argparse.ArgumentParser(description="Enix/Wenix outreach pre-send deduplication and compliance gate")
    parser.add_argument("--db",default="outreach/private/leads.sqlite3")
    cmd=parser.add_subparsers(dest="cmd",required=True)
    imp=cmd.add_parser("import")
    imp.add_argument("--file",required=True); imp.add_argument("--brand",choices=BRANDS,required=True)
    imp.add_argument("--source",default="business-site-research")
    ap=cmd.add_parser("approve")
    ap.add_argument("--id",type=int,required=True); ap.add_argument("--basis",required=True)
    sup=cmd.add_parser("suppress")
    g=sup.add_mutually_exclusive_group(required=True); g.add_argument("--email"); g.add_argument("--company")
    sup.add_argument("--reason",default="Do not contact")
    exp=cmd.add_parser("export")
    exp.add_argument("--brand",choices=BRANDS,required=True); exp.add_argument("--out",required=True)
    exp.add_argument("--limit",type=int,default=8); exp.add_argument("--confirmed",action="store_true")
    m=cmd.add_parser("mark")
    m.add_argument("--email",required=True); m.add_argument("--status",required=True,
      choices=("sent","replied","bounced","opted_out","release")); m.add_argument("--provider-id",default="")
    hist=cmd.add_parser("import-history"); hist.add_argument("--file",required=True)
    cmd.add_parser("report")
    args=parser.parse_args()
    db=open_db(args.db)
    if args.cmd=="import": result=import_csv(db,args.file,args.brand,args.source)
    elif args.cmd=="approve": approve(db,args.id,args.basis); result="approved"
    elif args.cmd=="suppress": result=suppress(db,"email" if args.email else "company",args.email or args.company,args.reason)
    elif args.cmd=="export": result={"exported":export_csv(db,args.brand,args.out,args.limit,args.confirmed),"path":args.out}
    elif args.cmd=="mark": result=mark(db,args.email,args.status,args.provider_id)
    elif args.cmd=="import-history": result={"suppressed_previous_contacts":import_history(db,args.file)}
    else: result=report(db)
    print(result)
    db.close()

if __name__=="__main__":
    main()
