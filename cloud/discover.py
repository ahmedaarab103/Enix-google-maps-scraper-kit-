"""Permissioned business discovery through official Google Places API.
Writes only business names/locations/websites; NO contact emails are invented or sent.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse
import gspread
from google.oauth2.service_account import Credentials

def main():
    if os.getenv("ENIX_DISCOVERY_ENABLED","").lower() != "true":
        print("Discovery disabled; no API calls.")
        return
    api_key=os.getenv("GOOGLE_PLACES_API_KEY")
    secret=os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sid=os.getenv("GOOGLE_SHEET_ID")
    if not all([api_key,secret,sid]):
        raise RuntimeError("Places API key, private sheet ID and service-account JSON required")
    query=os.getenv("ENIX_DISCOVERY_QUERY","hotels in Marrakech Morocco")
    endpoint="https://places.googleapis.com/v1/places:searchText"
    data=json.dumps({"textQuery":query,"pageSize":10}).encode()
    req=urllib.request.Request(endpoint,data=data,method="POST",headers={
        "Content-Type":"application/json",
        "X-Goog-Api-Key":api_key,
        "X-Goog-FieldMask":"places.id,places.displayName,places.formattedAddress,places.websiteUri"})
    with urllib.request.urlopen(req,timeout=30) as resp:
        places=json.load(resp).get("places",[])
    creds=Credentials.from_service_account_info(json.loads(secret),
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    ws=gspread.authorize(creds).open_by_key(sid).worksheet("Leads")
    grid=ws.get_all_values()
    headers=[str(x).strip() for x in grid[0]]
    current=[dict(zip(headers,row+[""]*(len(headers)-len(row)))) for row in grid[1:]]
    known={r.get("website","").strip().lower().rstrip("/") for r in current if r.get("website")}
    known_name={(r.get("company","").strip().lower(),r.get("city","").strip().lower()) for r in current}
    count=0
    for place in places:
        name=place.get("displayName",{}).get("text","").strip()
        website=place.get("websiteUri","").strip()
        loc=place.get("formattedAddress","").strip()
        city=query.rsplit(" in ",1)[-1].split(",")[0].strip()
        if not name: continue
        domain=urlparse(website).netloc.lower()
        if website and website.lower().rstrip("/") in known: continue
        if (name.lower(),city.lower()) in known_name: continue
        row={h:"" for h in headers}
        row.update({"company":name,"industry":query.split(" in ")[0],
                    "city":city,"country":"Morocco","website":website,
                    "source_url":"https://www.google.com/maps/place/?q=place_id:"+place.get("id",""),
                    "status":"NEW","approved":"NO",
                    "notes":"Official Places API business lead; verify contact independently"})
        ws.append_row([row[h] for h in headers],value_input_option="RAW")
        known.add(website.lower().rstrip("/"))
        known_name.add((name.lower(),city.lower()))
        count+=1
    print("New business leads:",count,"(none were emailed)")
if __name__=="__main__":
    main()
