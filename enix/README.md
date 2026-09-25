# Enix Outreach Pipeline

This folder turns Google Maps scrape results into a clean, deduplicated and scored prospect list for Enix.

## 1. Scrape one target segment

Start the local scraper:

```bash
docker compose up -d
```

Hospitality example:

```powershell
py scripts\scrape.py --keywords-file enix\keywords\hospitality.txt --city "Marrakech, Morocco" --depth 5 --socials --out out\hospitality-raw.csv
```

Repeat with:

- `enix/keywords/travel-tourism.txt`
- `enix/keywords/events.txt`
- `enix/keywords/real-estate.txt`

Keep jobs conservative: one at a time, depth 5 initially.

## 2. Dedupe + qualify

```powershell
py enix\prepare_leads.py out\hospitality-raw.csv
```

Outputs:

- `out/enix-leads.csv` — all unique processed businesses
- `out/enix-qualified.csv` — only businesses above the configured threshold that have an email

## 3. How Enix scoring works

The deterministic score favors:

- contactable businesses
- active websites/social presence
- Enix target sectors
- Marrakech businesses
- stronger Google ratings/review volume

It does **not** automatically decide who should receive an email. The score prioritizes which leads should be researched first.

## 4. Outreach workflow

Recommended statuses:

`NEW → RESEARCHED → READY_TO_CONTACT → CONTACTED → FOLLOWUP_1 → FOLLOWUP_2 → REPLIED`

Terminal statuses:

`INTERESTED / NOT_INTERESTED / BOUNCED / DO_NOT_CONTACT`

Before sending, check:

1. The business is still relevant.
2. The email is a suitable public business contact.
3. There is no existing Enix conversation.
4. The prospect has not opted out.
5. A real website/business observation exists for personalization.

## 5. Google Sheets handoff

Import `out/enix-qualified.csv` into the Enix Outreach CRM Google Sheet.

The extra columns are intentionally CRM-ready:

- Enix segment
- qualification score
- reason for fit
- recommended service
- language
- personalization observation
- email subject/body
- contact/follow-up dates
- reply status
- notes

## 6. Sending strategy

Start small: approximately 5 new, researched prospects per weekday.

Follow-up policy:

- Follow-up 1: around 4 business days after first contact
- Follow-up 2: around 7 business days after follow-up 1
- Stop immediately when the prospect replies
- Never send more than 2 follow-ups
