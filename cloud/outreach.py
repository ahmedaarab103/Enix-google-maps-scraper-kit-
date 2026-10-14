"""ENIX cautious, approved-only cloud outreach runner.

No first-contact or follow-up is sent without YES approval on its row and
an explicit repo variable ENIX_SEND_ENABLED=true.
"""
import json
import os
import ssl
import smtplib
import imaplib
import email
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import gspread
from google.oauth2.service_account import Credentials

UTC = timezone.utc
NOW = datetime.now(UTC)
SENDER = os.environ.get("SMTP_USER", "").strip().lower()
ACTIVE = os.environ.get("ENIX_SEND_ENABLED", "").lower() == "true"

def dateval(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    except ValueError:
        return None

def sheet():
    secret = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    sid = os.environ.get("GOOGLE_SHEET_ID")
    if not secret or not sid:
        raise RuntimeError("Missing Google Sheet credentials: runner cannot safely proceed.")
    creds = Credentials.from_service_account_info(
        json.loads(secret), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(creds).open_by_key(sid)

def rows(ws):
    vals = ws.get_all_values()
    headers = [h.strip() for h in vals[0]]
    return headers, [(i, dict(zip(headers, r + [""] * (len(headers)-len(r)))))
                     for i, r in enumerate(vals[1:], start=2)]

def patch(ws, headers, i, changes):
    for key, value in changes.items():
        ws.update_cell(i, headers.index(key)+1, str(value))

def log(ws, addr, company, event, detail="", mid=""):
    ws.append_row([NOW.isoformat(), addr, company, event, detail[:300], mid],
                  value_input_option="RAW")

def check_reply_addresses(host, user, pwd):
    if not all([host,user,pwd]):
        raise RuntimeError("Missing IMAP credentials; refusing to send without reply check.")
    found = set()
    with imaplib.IMAP4_SSL(host) as imap:
        imap.login(user, pwd)
        status, _ = imap.select("INBOX", readonly=True)
        if status != "OK":
            raise RuntimeError("Cannot select inbox")
        since = (NOW - timedelta(days=90)).strftime("%d-%b-%Y")
        status, data = imap.search(None, "SINCE", since)
        if status != "OK":
            raise RuntimeError("Reply check failed")
        for uid in data[0].split():
            typ, res = imap.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM)])")
            if typ != "OK" or not res or not isinstance(res[0],tuple):
                continue
            header = email.message_from_bytes(res[0][1])
            address = parseaddr(header.get("From",""))[1].lower().strip()
            if address:
                found.add(address)
    return found

def is_valid(addr):
    return "@" in addr and "." in addr.split("@")[-1] and all(
        c not in addr for c in [" ","\n","\r",",",";"])

def main():
    book = sheet()
    leads = book.worksheet("Leads")
    suppression = book.worksheet("Suppression")
    activity = book.worksheet("Activity")
    h, items = rows(leads)
    _, blocked = rows(suppression)
    _, history = rows(activity)
    _, config_rows = rows(book.worksheet("Config"))
    config = {r.get("key","").strip(): r.get("value","").strip() for _,r in config_rows}
    # Require the independent private-Sheet switch as well as the GitHub variable.
    enabled = ACTIVE and config.get("outbound_enabled", "").upper() == "TRUE"
    deny = {r.get("email","").strip().lower() for _,r in blocked}
    # First contacts must not be retried across restarts; existing SENT rows remain eligible for approved follow-ups.
    already_first = {r.get("email","").strip().lower()
        for _,r in history if r.get("event","") in ("RESERVED","SENT")}
    # A successful email generates both RESERVED and SENT events; count its message ID once.
    accepted_events = ("RESERVED", "SENT", "FOLLOWUP_1", "FOLLOWUP_2")
    today = NOW.date().isoformat()
    used = len({r.get("message_id","") or
               (r.get("timestamp_utc","") + ":" + r.get("email","") + ":" + r.get("event",""))
               for _,r in history if r.get("timestamp_utc","").startswith(today)
               and r.get("event","") in accepted_events})
    # A reserved message with no terminal result might already have left SMTP.
    # Never retry automatically; require manual reconciliation with the Sent folder.
    committed = {r.get("message_id","") for _,r in history if r.get("event","") in
                 ("SENT","FOLLOWUP_1","FOLLOWUP_2","ERROR") and r.get("message_id","")}
    pending = {r.get("email","").strip().lower() for _,r in history
               if r.get("event","") == "RESERVED" and r.get("message_id","") not in committed}
    weekday = NOW.astimezone(ZoneInfo("Africa/Casablanca")).weekday()
    hour = NOW.astimezone(ZoneInfo("Africa/Casablanca")).hour
    if weekday >= 5 or not 9 <= hour <= 16:
        print("Outside permitted Morocco business hours")
        return
    if used >= 10:
        print("Daily cap reached")
        return
    if not enabled:
        print("DRY RUN ONLY: at least one send switch disabled")
    replies = check_reply_addresses(os.environ.get("IMAP_HOST",""),
                                     SENDER, os.environ.get("SMTP_PASS",""))
    if not SENDER or not is_valid(SENDER):
        raise RuntimeError("Invalid authenticated sending address.")
    if enabled and not SENDER.endswith("@enix.ma"):
        raise RuntimeError("Refusing to send from non-Enix address.")
    sent_new, sent_total = 0, 0
    duplicate_guard = set()
    for index,row in items:
        addr = row.get("email","").strip().lower()
        if not is_valid(addr) or addr in duplicate_guard:
            continue
        duplicate_guard.add(addr)
        if addr in deny or addr in pending or row.get("status","").upper() in ("OPTED_OUT","BOUNCED","REPLIED","DONE"):
            continue
        if addr in replies:
            if row.get("status","").upper() not in ("REPLIED","DONE"):
                patch(leads,h,index,{"status":"REPLIED","last_reply_utc":NOW.isoformat()})
            continue
        if row.get("approved","").upper() != "YES" or used + sent_total >= 10 or sent_total >= 8:
            continue
        status = row.get("status","").upper()
        count = int(row.get("followup_count","0") or 0)
        first = status == "READY" and addr not in already_first and sent_new < 5
        previous = dateval(row.get("last_sent_utc",""))
        gap = timedelta(days=3 if count == 0 else 5)
        follow = status == "SENT" and 0 <= count < 2 and previous and NOW-previous >= gap
        if not (first or follow):
            continue
        subject = row.get("subject","").strip()
        body = row.get("body","").strip()
        if not subject or not body or "\n" in subject or "\r" in subject:
            continue
        if follow:
            subject = subject if subject.lower().startswith("re:") else "Re: "+subject
            body = ("Bonjour, je reviens brièvement sur mon message précédent. "
                    "Seriez-vous la bonne personne pour en discuter ?\n\n"
                    "Si ce n’est pas pertinent, dites-le-moi et je ne vous relancerai pas.\n\n"
                    "Houssaine OULAHYANE\nEnix")
        if not enabled:
            print("DRY RUN eligible row",index,"kind",("FIRST" if first else "FOLLOWUP"))
            continue
        mid = make_msgid(domain="enix.ma")
        # Reserve before network send; if it crashes after this, do not resend automatically.
        log(activity,addr,row.get("company",""),"RESERVED",
            "FIRST" if first else "FOLLOWUP",mid)
        msg = EmailMessage()
        msg["From"]=SENDER; msg["To"]=addr; msg["Subject"]=subject
        msg["Message-ID"]=mid
        msg.set_content(body)
        try:
            port = int(os.environ.get("SMTP_PORT","465"))
            host = os.environ["SMTP_HOST"]
            if port == 465:
                con = smtplib.SMTP_SSL(host,port,context=ssl.create_default_context(),timeout=25)
            else:
                con = smtplib.SMTP(host,port,timeout=25)
                con.starttls(context=ssl.create_default_context())
            with con:
                con.login(SENDER,os.environ["SMTP_PASS"])
                con.send_message(msg)
        except Exception as err:
            log(activity,addr,row.get("company",""),"ERROR",type(err).__name__,mid)
            patch(leads,h,index,{"status":"ERROR","last_error":type(err).__name__})
            continue
        event = "SENT" if first else "FOLLOWUP_"+str(count+1)
        log(activity,addr,row.get("company",""),event,"SMTP accepted",mid)
        patch(leads,h,index,{"status":"SENT","last_sent_utc":NOW.isoformat(),
              "first_sent_utc":row.get("first_sent_utc","") or NOW.isoformat(),
              "followup_count":count+(0 if first else 1),"last_message_id":mid,
              "last_error":""})
        sent_total += 1
        if first: sent_new += 1
    print("Outbound sent:",sent_total)

if __name__=="__main__":
    main()
