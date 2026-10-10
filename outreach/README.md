# Enix + Wenix outreach: safe foundation (NOT LIVE)

This folder adds a provider-independent, zero-dependency pre-send safety gate to the existing scraper project. It does NOT scrape businesses, authenticate mailboxes, schedule mail, or send anything. Do not describe this branch as an active automation.

## Sending decision

- Do not use Resend for unsolicited cold email: its acceptable-use rules prohibit cold outreach and scraped lists.
- Do not use Hostinger Mail for unsolicited cold email: its mass-mailing policy permits solicited email only.
- WENIX's existing normal-business mailbox is at **Zoho Mail** (user-confirmed). Zoho Mail's September 2, 2026 usage policy explicitly prohibits promotional, marketing, bulk, and automated emails, so do NOT connect that mailbox to an automated cold outreach sequence. Preserve it for normal replies and business correspondence. The WENIX public sample config intentionally omits the full mailbox address. Check the exact mailbox and authentication privately before any one-to-one use.
- For relevant, lawful B2B outreach, consider Apollo (already connected to ChatGPT but no mailboxes connected as of 2026-10-10), or Smartlead. Sending mailboxes must also permit the activity. Follow applicable laws and provider policies.
- No provider can promise a mailbox will never be rate-limited.
- Google Maps scraping can violate Google's Terms of Service. The existing scraper remains available but is not run or scheduled here. Use data collected with appropriate permission or a licensed/independently verified B2B research source instead.

## Funnels

ENIX: events, conferences, hotels, riads, travel, hospitality, photography and video. Cities: Casablanca, Rabat, Tangier, Marrakech, Agadir, Dakhla, Laayoune.

WENIX: website redesign, development, SEO, GEO, conversion, branding and marketing. Research qualified Moroccan businesses with actual website or visibility needs.

Keep contact data, sending credentials and outreach history OUT of this public GitHub repository.

## Pre-send gate (Python 3.10+, stdlib only)

The existing scraper produces CSV fields such as title, emails, website, category, address. The importer recognizes those columns. It can also accept licensed CSVs. No Docker is required for the importer; the original scraper retains its own runtime.

Run from repository root, using private paths:

    python outreach/pipeline.py import --brand ENIX --file path/to/enix-leads.csv
    python outreach/pipeline.py import --brand WENIX --file path/to/wenix-leads.csv
    python outreach/pipeline.py import-history --file path/to/previously-sent.csv
    python outreach/pipeline.py suppress --company example.com --reason "Do not contact"
    python outreach/pipeline.py report

Every imported contact starts in status new and is not eligible for outreach, regardless of source CSV columns. Email and company identity are globally unique across both brands.

After verifying the contact and documenting the applicable legal basis:

    python outreach/pipeline.py approve --id 1 --basis "Individually verified B2B business contact with documented relevance and lawful basis"
    python outreach/pipeline.py export --brand ENIX --out outreach/private/enix-review.csv --limit 8 --confirmed
    python outreach/pipeline.py export --brand WENIX --out outreach/private/wenix-review.csv --limit 8 --confirmed

Export is a reservation, NOT an email send. The same lead cannot be exported again without an explicit release. The demonstration cap is 10 reservations per brand per UTC day; use stricter sender limits as needed.

After the sender acknowledges an email, store its real provider message ID:

    python outreach/pipeline.py mark --email qualified@example.com --status sent --provider-id actual-id

Record replies, bounces, opt-outs and exclusion immediately:

    python outreach/pipeline.py mark --email qualified@example.com --status replied
    python outreach/pipeline.py mark --email qualified@example.com --status bounced
    python outreach/pipeline.py mark --email qualified@example.com --status opted_out

For an unsent reservation ONLY, review provider logs before releasing:

    python outreach/pipeline.py mark --email qualified@example.com --status release

Never auto-retry an ambiguous provider timeout.

## Migration is mandatory

Before launch export ALL historical ENIX contacts from both Hostinger Sent and Resend as well as any previous WENIX outbound records. Use the import-history command with a CSV containing email or to or recipient. This produces permanent global suppression for previously contacted addresses. Also suppress companies under manual discussions, active clients, and companies that opted out. Never commit the resulting database.

## Mailboxes / sequences

1. Link two different, authorized outreach mailboxes to Apollo or another purpose-built sequencer. Do not route unsolicited or automated cold outreach through Resend, Hostinger Mail, **or Zoho Mail**. Keep Enix's Hostinger contact inbox and Wenix's Zoho business inbox for normal client correspondence. Mailbox providers must explicitly permit the intended prospecting before connecting.
2. Verify MX (where applicable), SPF, DKIM and DMARC alignment and public domain resolution. Address any Sender Domain Not Found errors first.
3. Leave sequences INACTIVE until sender policies, mailbox status, contact permissions and recipient data all pass review.
4. Sequence: day 0 initial; day 3 first follow-up; day 8 final follow-up. Stop on reply, booking, unsubscribe, bounce, or out-of-office hold. Use company-level reply pause where supported.
5. Start with a conservative illustrative 5-10 new contacts per day per mailbox, plus follow-ups. This is NOT a quota guarantee and should be adjusted to provider policy, reputation and observed delivery.
6. Plain text, personalized, factual, accurate brand identity, unobtrusive opt-out. Do not claim an audit was completed when it wasn't.
7. Keep per-brand sender IDs and separate campaign reporting but one shared contact/company suppression history.

## Cloud deployment still outstanding

This current proof of concept keeps its private SQLite database on the execution machine. It is NOT an unattended cloud deployment.

Recommended production architecture: licensed lead data / approved CSV import -> Cloudflare Worker job -> durable Cloudflare D1 or managed PostgreSQL -> atomic company/contact reservation -> approved sender (Apollo/Smartlead) -> verified status/reply webhooks -> global suppression + alerts. The inbound email webhook must verify signature and treat incoming content as untrusted data. No email text should command automated actions without deterministic authorization checks.

Dependencies for actual launch: private cloud database and deployment, compliant lead data source, two approved mailboxes, provider connectivity, historical-sends import, sending domain checks, message approval, integration tests. No emails have been sent by this branch.
