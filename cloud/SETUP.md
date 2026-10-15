# ENIX cloud infrastructure — current owner checklist

Two separate pieces:
1. **Lightning AI** = existing scraper, cautious discovery, private CRM insert. See [LIGHTNING_SETUP.md](LIGHTNING_SETUP.md).
2. **GitHub Actions + Hostinger** = approved-only email sender. Off by default. This remains separate from Lightning because Lightning's acceptable-use rules restrict unsolicited email.

Google **Places** API is **not** required. Google **Sheets** API/service account is required for automatic CRM writes from either cloud service.

## Private CRM

Use the ENIX CRM spreadsheet in your connected Google account:
https://docs.google.com/spreadsheets/d/1CD7ZNQKI2oQu6L-i4m4kVGT4f-sNAwbD0n662PZr2Ms/edit

Tabs: Leads, Suppression, Activity, Config.
Discovery: new leads are status NEW and approved NO. No emails are collected by the initial scraper run.
Config values `discovery_enabled=FALSE` and `outbound_enabled=FALSE` must stay FALSE until independently authorized.
The scraper uses an additional `scraper_last_started_utc` marker to avoid repeating runs within 24 hours.

## Lightning discovery

Read `cloud/LIGHTNING_SETUP.md`.
No Google Places key, no Google billing needed for the scraper itself.
Run the offline unit tests and sample CSV dry run first; then verify Docker `localhost:8080` availability. Use minimal allowed volume and respect Google's terms; stop if blocked. The live runner requires encrypted private Sheets credentials and two discovery enabling switches.

## GitHub Actions email sender (NOT LIVE)

In repository Actions secrets (not chat or committed code), configure:
- ENIX_GOOGLE_SERVICE_ACCOUNT_JSON
- ENIX_GOOGLE_SHEET_ID
- ENIX_SMTP_HOST, ENIX_SMTP_PORT
- ENIX_SMTP_USER, ENIX_SMTP_PASS
- ENIX_IMAP_HOST

In repository Actions variables:
- ENIX_SEND_ENABLED=false

Do not change the variable to true until:
1. Service-account access to private CRM is verified.
2. Hostinger SMTP and IMAP credentials are tested safely.
3. Bounces and unsubscribes are accounted for.
4. Sending test to an owner-controlled address passes.
5. Owner explicitly approves outbound sending.

The GitHub sender also requires Config `outbound_enabled=TRUE`. No email goes out unless both switches are enabled and individual leads are approved YES.

Safety: Weekdays during Morocco business hours, up to 5 new / 8 total per run and 10/day, no automated retry of unknown sends, two follow-ups at most, opt-out and reply exclusions.

## Status

- Offline GitHub unit tests passed, including scraper simulation.
- Lightning's earlier 13 tests passed according to the owner-controlled extension; newly added tests must be re-run there.
- No real scrape or unattended sending has been verified/activated through this branch.
- The previous Google Places scheduled workflow has been removed from this branch.
- Public repository must never contain secrets or personal lead datasets.
