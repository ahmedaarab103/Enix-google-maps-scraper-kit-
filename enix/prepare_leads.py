#!/usr/bin/env python3
"""Prepare Google Maps scrape results for Enix high-ticket outreach."""
import argparse, csv, json, re
from pathlib import Path
from urllib.parse import urlparse

STATUS_NEW = "NEW"

def load_config(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def clean(v):
    return (v or "").strip()

def normalize_domain(url):
    url = clean(url).lower()
    if not url: return ""
    if "://" not in url: url = "http://" + url
    try: host = urlparse(url).netloc.lower()
    except Exception: return ""
    if host.startswith("www."): host = host[4:]
    return host.split(":")[0]

def normalize_phone(phone):
    return re.sub(r"\D+", "", clean(phone))

def normalize_email(value):
    value = clean(value).lower()
    for part in re.split(r"[;,\s]+", value):
        if "@" in part and "." in part.rsplit("@", 1)[-1]:
            return part
    return ""

def slug(value):
    return re.sub(r"[^a-z0-9]+", " ", clean(value).lower()).strip()

def dedupe_key(row):
    domain = normalize_domain(row.get("website"))
    if domain: return "domain:" + domain
    email = normalize_email(row.get("emails"))
    if email: return "email:" + email
    phone = normalize_phone(row.get("phone"))
    if phone: return "phone:" + phone
    return "fallback:" + slug(row.get("title")) + "|" + slug(row.get("address"))

def parse_float(v):
    try: return float(str(v).replace(",", ".").strip())
    except Exception: return 0.0

def parse_int(v):
    try: return int(float(str(v).replace(",", "").strip()))
    except Exception: return 0

def combined_text(row):
    return " ".join([
        clean(row.get("title")), clean(row.get("category")),
        clean(row.get("address")), clean(row.get("website"))
    ]).lower()

def classify_segment(row, config):
    haystack = combined_text(row)
    best, best_hits = None, 0
    for seg in config["segments"]:
        hits = sum(1 for p in seg["patterns"] if p.lower() in haystack)
        if hits > best_hits:
            best, best_hits = seg, hits
    if best:
        return best["name"], best["service"], best_hits
    return "Other", "Photography, videography and visual production", 0

def score_row(row, config):
    w = config["weights"]
    score, reasons = 0, []
    email = normalize_email(row.get("emails"))
    domain = normalize_domain(row.get("website"))
    rating = parse_float(row.get("review_rating"))
    reviews = parse_int(row.get("review_count"))
    haystack = combined_text(row)
    segment, service, segment_hits = classify_segment(row, config)

    checks = [
        (bool(email), "email", "email available"),
        (bool(domain), "website", "website available"),
        (bool(clean(row.get("instagram"))), "instagram", "Instagram found"),
        (bool(clean(row.get("linkedin"))), "linkedin", "LinkedIn found"),
        (segment_hits > 0, "target_segment", "matches Enix high-ticket segment"),
        (rating >= 4.3, "rating_4_3_plus", "rating >= 4.3"),
        (rating >= 4.6, "rating_4_6_plus_bonus", "rating >= 4.6"),
        (reviews >= 25, "reviews_25_plus", "25+ reviews"),
        (reviews >= 100, "reviews_100_plus_bonus", "100+ reviews"),
        (reviews >= 300, "reviews_300_plus_bonus", "300+ reviews"),
        (any(a in haystack for a in config.get("market_aliases", [])), "target_market_address", "Casablanca market"),
        (any(t in haystack for t in config.get("high_ticket_terms", [])), "high_ticket_signal", "high-ticket positioning signal")
    ]
    for ok, key, reason in checks:
        if ok:
            score += w[key]
            reasons.append(reason)
    return score, segment, service, reasons, email, domain

def process(rows, config):
    seen, out = set(), []
    for raw in rows:
        key = dedupe_key(raw)
        if key in seen: continue
        seen.add(key)
        score, segment, service, reasons, email, domain = score_row(raw, config)
        row = dict(raw)
        row.update({
            "primary_email": email,
            "website_domain": domain,
            "enix_segment": segment,
            "qualification_score": score,
            "qualification_reasons": "; ".join(reasons),
            "recommended_service": service,
            "status": STATUS_NEW,
            "language": config.get("default_language_hint", "FR"),
            "personalization_observation": "",
            "email_subject": "",
            "email_body": "",
            "first_contact_date": "",
            "followup_1_date": "",
            "followup_2_date": "",
            "reply_status": "",
            "notes": ""
        })
        out.append(row)
    out.sort(key=lambda r: int(r["qualification_score"]), reverse=True)
    return out

def write_csv(path, rows, fieldnames):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)

def main():
    ap = argparse.ArgumentParser(description="Dedupe and score Google Maps leads for Enix.")
    ap.add_argument("input")
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
    qualified = [r for r in processed if int(r["qualification_score"]) >= min_score and r["primary_email"]]

    base = list(rows[0].keys()) if rows else ["title","phone","emails","website","category","address","review_rating","review_count"]
    extra = ["primary_email","website_domain","enix_segment","qualification_score","qualification_reasons",
             "recommended_service","status","language","personalization_observation","email_subject","email_body",
             "first_contact_date","followup_1_date","followup_2_date","reply_status","notes"]
    fields = base + [x for x in extra if x not in base]
    write_csv(args.out, processed, fields)
    write_csv(args.qualified_out, qualified, fields)

    print(f"Input rows: {len(rows)}")
    print(f"Unique leads: {len(processed)}")
    print(f"Qualified + email: {len(qualified)} (score >= {min_score})")
    print(f"All leads -> {args.out}")
    print(f"Qualified -> {args.qualified_out}")

if __name__ == "__main__":
    main()
