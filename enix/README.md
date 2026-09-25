# Enix Outreach Pipeline — Casablanca High Ticket

The current focus is **Casablanca** and **higher-ticket prospects**.

Priority segments:
1. Premium / luxury real-estate developers and agencies
2. 4–5 star hotels with events, MICE and premium hospitality
3. Corporate event agencies and premium event venues
4. Premium travel, DMC and concierge companies

## First scrape

Start Docker:

```bash
docker compose up -d
```

Run the high-ticket Casablanca pack:

```powershell
py scripts\scrape.py --keywords-file enix\keywords\casablanca-high-ticket.txt --city "Casablanca, Morocco" --depth 5 --socials --out out\casablanca-high-ticket-raw.csv
```

Then dedupe and score:

```powershell
py enix\prepare_leads.py out\casablanca-high-ticket-raw.csv --out out\casablanca-all.csv --qualified-out out\casablanca-qualified.csv
```

Use `out/casablanca-qualified.csv` as the prospect pool for research and cold email.

## High-ticket qualification

The score prioritizes:
- public business email
- real website
- target high-ticket sector
- Casablanca presence
- premium/luxury/corporate signals
- social presence
- healthy rating/review volume

A high score is a **research priority**, not an automatic permission to email.

## Outreach stages

`NEW → RESEARCHED → READY_TO_CONTACT → CONTACTED → FOLLOWUP_1 → FOLLOWUP_2 → REPLIED`

Terminal states:

`INTERESTED / NOT_INTERESTED / BOUNCED / DO_NOT_CONTACT`

Before outreach, verify the business, use an appropriate public business contact, check previous Enix conversations, and create one real personalization observation.

Start with approximately 5 researched new contacts per weekday while sender reputation and response quality are being validated.
