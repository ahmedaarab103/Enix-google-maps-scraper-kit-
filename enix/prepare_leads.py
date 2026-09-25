#!/usr/bin/env python3
"""Prepare Google Maps scrape results for Enix outreach.

Input: CSV produced by scripts/scrape.py (preferably with --socials).
Output:
  - all processed/deduplicated leads
  - qualified leads only

Uses only Python stdlib.
"""
import argparse
import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse


STATUS_NEW = "NEW"


def load_config(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def clean(value):
    return (value or "").strip()


def normalize_domain(url):
    url = clean(url).lower()
    if not url:
        return ""
    if "://" not in url:
        url = "http://" + url
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host.split(":")[0]


def normalize_phone(phone):
    return re.sub(r"\D+", "", clean(phone))


def normalize_email(email_field):
    value = clean(email_field).lower()
    if not value:
        return ""
    # scraper sometimes returns one address and sometimes a delimited field
    for part in re.split(r"[;,\s]+", value):
        if "@" in part and "." in part.rsplit("@", 1)[-1]:
            return part
    return ""


def slug(value):
    return re.sub(r"[^a-z0-9]+", " ", clean(value).lower()).strip()


def dedupe_key(row):
    domain = normalize_domain(row.get("website"))
    if domain:
        return "domain:" + domain
    email = normalize_email(row.get("emails"))
    if email:
        return "email:" + email
    phone = normalize_phone(row.get("phone"))
    if phone:
        return "phone:" + phone
    title = slug(row.get("title"))
    address = slug(row.get("address"))
    return "fallback:" + title + "|" + address


def parse_float(value):
    try:
        return float(str(value).replace(",", ".").strip())
    except Exception:
        return 0.0


def parse_int(value):
    try:
        return int(float(str(value).replace(",", "").strip()))
    except Exception:
        return 0


def classify_segment(row, config):
    haystack = " ".join([
        clean(row.get("title")),
        clean(row.get("category")),
        clean(row.get("address"))
    ]).lower()

    best = None
    best_hits = 0
    for seg in config["segments"]:
        hits = sum(1 for p in seg["patterns"] if p.lower() in haystack)
        if hits > best_hits:
            best, best_hits = seg, hits

    if best:
        return best["name"], best["service"], best_hits
    return "Other", "Visual production, photography and videography", 0


def score_row(row, config):
    w = config["weights"]
    score = 0
    reasons = []

    email = normalize_email(row.get("emails"))
    domain = normalize_domain(row.get("website"))
    instagram = clean(row.get("instagram"))
    linkedin = clean(row.get("linkedin"))
    rating = parse_float(row.get("review_rating"))
    reviews = parse_int(row.get("review_count"))
    address = clean(row.get("address")).lower()

    segment, service, segment_hits = classify_segment(row, config)

    if email:
        score += w["email"]; reasons.append("email available")
    if domain:
        score += w["website"]; reasons.append("website available")
    if instagram:
        score += w["instagram"]; reasons.append("Instagram found")
    if linkedin:
        score += w["linkedin"]; reasons.append("LinkedIn found")
    if segment_hits:
        score += w["target_segment"]; reasons.append("matches Enix target segment")
    if rating >= 4.3:
        score += w["rating_4_3_plus"]; reasons.append("rating >= 4.3")
    if rating >= 4.6:
        score += w["rating_4_6_plus_bonus"]; reasons.append("rating >= 4.6")
    if reviews >= 25:
        score += w["reviews_25_plus"]; reasons.append("25+ reviews")
    if reviews >= 100:
        score += w["reviews_100_plus_bonus"]; reasons.append("100+ reviews")
    if reviews >= 300:
        score += w["reviews_300_plus_bonus"]; reasons.append("300+ reviews")
    if "marrakech" in address or "marrakesh" in address:
        score += w["marrakech_address"]; reasons.append("Marrakech location")

    return score, segment, service, reasons, email, domain


def process(rows, config):
    seen = set()
    out = []

    for raw in rows:
        key = dedupe_key(raw)
        if key in seen:
            continue
        seen.add(key)

        score, segment, service, reasons, email, domain = score_row(raw, config)

        row = dict(raw)
        row["primary_email"] = email
        row["website_domain"] = domain
        row["enix_segment"] = segment
        row["qualification_score"] = score
        row["qualification_reasons"] = "; ".join(reasons)
        row["recommended_service"] = service
        row["status"] = STATUS_NEW
        row["language"] = config.get("default_language_hint", "FR")
        row["personalization_observation"] = ""
        row["email_subject"] = ""
        row["email_body"] = ""
        row["first_contact_date"] = ""
        row["followup_1_date"] = ""
        row["followup_2_date"] = ""
        row["reply_status"] = ""
        row["notes"] = ""
        out.append(row)

    out.sort(key=lambda r: int(r["qualification_score"]), reverse=True)
    return out


def write_csv(path, rows, fieldnames):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Dedupe and qualify Google Maps leads for Enix outreach.")
    ap.add_argument("input", help="CSV generated by scripts/scrape.py")
    ap.add_argument("--config", default="enix/config.json")
    ap.add_argument("--out", default="out/enix-leads.csv")
    ap.add_argument("--qualified-out", default="out/enix-qualified.csv")
    ap.add_argument("--min-score", type=int, default=None)
    args = ap.parse_args()

    config = load_config(args.config)
    min_score = args.min_score if args.min_score is not None else config["minimum_qualified_score"]

    with open(args.input, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    processed = process(rows, config)
    qualified = [
        r for r in processed
        if int(r["qualification_score"]) >= min_score and r["primary_email"]
    ]

    base_fields = list(rows[0].keys()) if rows else [
        "title","phone","emails","website","category","address","review_rating","review_count"
    ]
    extra_fields = [
        "primary_email","website_domain","enix_segment","qualification_score",
        "qualification_reasons","recommended_service","status","language",
        "personalization_observation","email_subject","email_body",
        "first_contact_date","followup_1_date","followup_2_date",
        "reply_status","notes"
    ]
    fields = base_fields + [x for x in extra_fields if x not in base_fields]

    write_csv(args.out, processed, fields)
    write_csv(args.qualified_out, qualified, fields)

    print(f"Input rows: {len(rows)}")
    print(f"Unique leads: {len(processed)}")
    print(f"Qualified + email: {len(qualified)} (score >= {min_score})")
    print(f"All leads -> {args.out}")
    print(f"Qualified -> {args.qualified_out}")


if __name__ == "__main__":
    main()
