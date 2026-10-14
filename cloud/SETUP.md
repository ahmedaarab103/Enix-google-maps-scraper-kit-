# ENIX cloud outreach — setup and safety

This workflow uses GitHub Actions as cloud compute (no computer or local Docker required). ChatGPT can manage repository changes and Hostinger messages; GitHub secrets/variables and Google Sheets access still require initial owner configuration.

## Required setup (before merging)
1. Import the ENIX CRM template into a **private Google Sheet**. Share with the service account as editor; create a Google service-account JSON credential with access limited to this Sheet. Never put credentials or lead data into this public repository.
2. In repository Actions secrets add:
   - ENIX_GOOGLE_SERVICE_ACCOUNT_JSON (complete JSON)
   - ENIX_GOOGLE_SHEET_ID (Sheet ID)
   - ENIX_SMTP_HOST and ENIX_SMTP_PORT (verify Hostinger settings)
   - ENIX_SMTP_USER, ENIX_SMTP_PASS
   - ENIX_IMAP_HOST
3. Repository Actions variable ENIX_SEND_ENABLED = false. **Do not turn on** until deliverability tests, successful dry run, and contacts approved. Set true only to authorize sending already approved rows.
4. Repository Actions variables ENIX_DISCOVERY_QUERY, ENIX_DISCOVERY_CITY for manual discovery jobs. Discovery is manual-only. Google Maps scraping may violate Google's terms; consider compliant Places API or permissioned data providers instead.
5. Current repo is public. Never enable artifact upload, console logging of lead data, or commit scraped data here.

## Sheet contract
Tabs: Leads, Suppression, Activity, Config. Fields are supplied in the CRM template. For sending, set status READY and approved YES with a real verified recipient email, personalized subject and body. Leave blank if unverified.
Activity logs are written for audit; Suppression holds opt-outs and do-not-contact.
Follow-ups require approved YES, are capped at two, and are skipped if replied, suppressed or invalid.

## Execution
Manual Actions > ENIX Cloud Outreach > Run workflow > mode=send will run an audit/dry-run while ENIX_SEND_ENABLED is false.
The same workflow runs weekday at 09:17 UTC. It stays in dry-run until turned on.
Discovery runs only by manual dispatch and does not send messages or publish raw scraped results.

## Safety and operational limits
No hidden mass sends. Small batches (max 5 new, 8 total per execution), weekday/time guard, hard per-day cap 10 based on Activity, domain/email dedupe, opt-outs, and replies checked over IMAP.
Turn off ENIX_SEND_ENABLED immediately if bounce rates, errors or complaints rise. No provider can guarantee deliverability.
The Google Sheet must be private, and access should be least privilege. Use an app-specific mailbox password if supported and revoke any old Sendvanta credentials.
