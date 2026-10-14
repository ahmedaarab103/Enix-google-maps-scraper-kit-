# ENIX — test in Lightning AI Studio (no live outreach)

This guide uses the user-owned Lightning account as a **development/testing environment**. It does **not** deploy the production cold-email sender to Lightning. Lightning's current terms restrict unsolicited/bulk email and some commercial activity without prior written consent. Keep production sending with Hostinger/GitHub Actions only after owner approval and service-provider policy review.

## 1. Start a free CPU Studio

Log in to https://lightning.ai and choose **New Studio**. Select the free CPU option if available in your account. Open its terminal. No GPU is needed.

## 2. Run the Enix offline smoke test

Paste these commands into the Studio terminal (no API keys or passwords):

```bash
git clone --branch feature/cloud-outreach-safe --single-branch https://github.com/ahmedaarab103/Enix-google-maps-scraper-kit-.git
cd Enix-google-maps-scraper-kit-
python -m pip install -r cloud/requirements.txt
python cloud/lightning_check.py
```

The check prints **13 tests**, finishing with **OK** and **PASS** when the environment works. It uses dummy companies and mocks email/network calls — nothing is scraped or sent.

If the directory already exists, use:
```bash
cd Enix-google-maps-scraper-kit-
git fetch origin feature/cloud-outreach-safe
git switch feature/cloud-outreach-safe
git pull --ff-only
python -m pip install -r cloud/requirements.txt
python cloud/lightning_check.py
```

## 3. Next steps after tests pass

- For actual permitted lead discovery, use the official Google Places API integration in `cloud/discover.py`. It requires Google Places API billing/key and private Google Sheets service-account access; it must not be run until provider terms, intended commercial use, and any needed permission are addressed.
- Store secrets in Lightning's encrypted **Teamspace > Settings > Secrets**, never in chat, GitHub or terminal history. Example names are `GOOGLE_PLACES_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_SHEET_ID`; don't add SMTP credentials to Lightning.
- To keep the first live run safe, retain `ENIX_DISCOVERY_ENABLED=false`, `ENIX_SEND_ENABLED=false`, and CRM Config `outbound_enabled=FALSE` until the full workflow has been reviewed.
- Lightning supports scheduled pipelines via the SDK; wait to schedule until a smoke test and data-processing approval succeed.
- We have not connected ChatGPT directly to the Lightning account; you can execute these exact commands yourself in its Studio UI, and the connected GitHub app can update the repository code.

## How to tell ChatGPT the result

Paste only the final output from `python cloud/lightning_check.py`, or share a screenshot of the Studio terminal. **Never send credentials or a screenshot containing secrets.**

## Official references

- https://lightning.ai/docs/platform/build/ai-studio
- https://lightning.ai/docs/platform/inference/pipelines/scheduling
- https://lightning.ai/docs/platform/security/security-features/secrets
- https://lightning.ai/legal/terms-and-conditions/
