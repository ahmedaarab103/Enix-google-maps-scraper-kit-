# ENIX — cautious existing scraper on Lightning AI (no Places API)

Enix uses the existing `gosom/google-maps-scraper` project via its own `scripts/scrape.py`, **not** the Google Places API. A low volume reduces the chance of rate-limits, but Google Maps scraping may violate Google's terms. Do not attempt to bypass captchas, blocks or rate limits. Stop after failed responses, and use an authorized alternative if access is disallowed.

This setup does NOT send cold emails. Keep sending through a separate, explicitly approved Hostinger/GitHub workflow. No SMTP credentials belong on Lightning AI.

## 1. Read and test safely (no credentials, no network)

In the EXISTING Lightning Studio terminal:

```bash
cd Enix-google-maps-scraper-kit-
git status --short
# IMPORTANT: if you have local changes, commit or stash them before pulling.
git fetch origin feature/cloud-outreach-safe
git switch feature/cloud-outreach-safe
git pull --ff-only
python -m pip install -r cloud/requirements.txt
python cloud/lightning_check.py
python cloud/discover_scraper.py --mode dry-run --input cloud/fixtures/sample_businesses.csv
```

The sample file contains invented companies and fake .example websites. No scraping, networking, API keys, CRM writes or emails occur in the dry-run. The unit tests should all pass. Do not hardcode the expected test count; it can increase as checks are added.

## 2. Check Docker / existing scraper availability

The original kit needs its scraper API on `localhost:8080`. Check:

```bash
docker info
docker compose version
```

If Docker daemon and Compose are available inside this Studio, the extension may start the pinned image with:

```bash
docker compose up -d
curl -fsS http://127.0.0.1:8080/api/v1/jobs
```

If `docker info` fails, DO NOT install a privileged daemon, expose port 8080 publicly, or make unsupported changes. Report the error and evaluate a supported Lightning Docker runtime / container, or keep scraper execution on GitHub Actions. Nothing should be exposed to the internet.

## 3. Private Google Sheets integration (only for automatic lead saving)

Google Places API credentials are **not needed**.

The CRM is:
https://docs.google.com/spreadsheets/d/1CD7ZNQKI2oQu6L-i4m4kVGT4f-sNAwbD0n662PZr2Ms/edit

Required **Lightning encrypted secrets**:
- `GOOGLE_SERVICE_ACCOUNT_JSON`: JSON of dedicated Google Sheets service account
- `GOOGLE_SHEET_ID`: spreadsheet ID from the URL above

Share the private CRM directly with that service-account email as Editor. Minimize access and protect key material; never paste private keys into chat, logs, or GitHub.

Keep the CRM Config tab `discovery_enabled=FALSE` during initial testing.

## 4. Minimal live scrape (manual approval REQUIRED)

The runner file is `cloud/discover_scraper.py`. Default behavior is offline dry-run. Live mode requires BOTH:
- Lightning environment variable `ENIX_DISCOVERY_ENABLED=true`
- Private CRM Config tab `discovery_enabled=TRUE`

It additionally requires credentials above and a working localhost scraper server.

Only after the owner approves a single trial (and understands Google terms), invoke:

```bash
python cloud/discover_scraper.py --mode live
```

Safeguards enforced:
- One small query: event organizers in Marrakech (Google Maps finds businesses, NOT event dates)
- Scraper depth 2, max job time 180 seconds
- Explicitly `--no-email` and only business title/site/category/address
- At most 10 unique event-organizer leads added to CRM, default NEW/approved NO, event dates blank, coverage_need UNKNOWN, priority RESEARCH
- De-duplication by website domain and company/city
- 24-hour no-retry marker in the private CRM Config tab
- No bypasses, proxies, CAPTCHA evasion, parallel jobs, automatic retry, or public lead artifacts
- Fail closed on missing secrets, disabled switches, inaccessible CRM or scraper errors
- Output CSV deleted after ingestion; logs show counts only

The guard is for accidental repeated calls, not a guarantee against every concurrent schedule race. Keep exactly one scheduled job with no overlaps.

## 5. Event-first qualification — prioritize REAL approaching events

Our focus is **corporate conferences, congresses, trade fairs, exhibitions, product launches, openings and established event management agencies**, initially Marrakech. The Maps scraper finds event companies, *not the dates of their upcoming conferences*.

For each organizer, research a **specific public upcoming event** from the organizer's official site or a credible event calendar. Enter these CRM Leads fields:
- `event_title`: title of the particular conference/exhibition/opening
- `event_date`: verified event start date in YYYY-MM-DD
- `event_source_url`: credible source showing the date and event
- `coverage_need`: UNKNOWN by default; OPEN_BRIEF only if organizer has *explicitly published a need for photography/videography suppliers*
- `coverage_need_source_url`: actual tender or supplier request documenting that need
- `priority`: initially RESEARCH; use the offline scoring logic after verification

Scoring is **evidence-based**, not a claim about a client without proof. `P1` means an independently documented open photo/video brief and event within 21 days. `P2` means confirmed event within 45 days but the need is unknown, or a later open brief. `P3` is a verified event within 90 days. Missing event date/source stays RESEARCH.

With Sheets secrets configured, review priorities without writing:
```bash
python cloud/score_event_leads.py
```
To write ONLY the priority field, after owner approval:
```bash
ENIX_SCORE_APPLY_ENABLED=true python cloud/score_event_leads.py --apply
```
No prospect is automatically approved or contacted. Do not fabricate dates, budgets, or supplier needs. Verify publicly listed business contact information and comply with opt-outs.

## 6. Scheduling (not yet activated)

Only after ONE successful manual run and CRM verification, propose a Lightning schedule no more than **twice weekly** initially, e.g. Tuesdays and Fridays at 08:30 UTC. Verify the actual Lightning SDK scheduling syntax and Studio session/runtime behavior before registering. Don't silently activate paid compute or scheduled jobs.

Set `ENIX_DISCOVERY_ENABLED=false` again after manual testing and until explicitly authorized to schedule.

## 7. Email automation stays separate

Enix's GitHub Actions sender requires its own authenticated SMTP/IMAP credentials and private-sheet setting `outbound_enabled=TRUE` *in addition* to GitHub var `ENIX_SEND_ENABLED=true`. Both are OFF by default and must remain so until a future approved outbound test.

## 8. Report to ChatGPT

Give:
- Docker info/Compose output, without tokens or credentials
- The last lines of offline test output
- A dry-run summary count
- Whether the private CRM service account is configured
- If/when explicitly approved, number of business leads added by ONE live test
- Any blocking error or extra cost needing approval

Do not claim that a live scrape or the CRM import is tested when only mocked tests have run.
