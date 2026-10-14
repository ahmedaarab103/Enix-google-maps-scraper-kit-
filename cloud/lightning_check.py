"""No-network, no-email smoke test for ENIX on Lightning AI Studio.

This entrypoint never invokes live discovery or SMTP. It prints no secret values.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAFE_KEYS = ("ENIX_DISCOVERY_ENABLED", "ENIX_SEND_ENABLED")
PRIVATE_KEYS = ("GOOGLE_PLACES_API_KEY", "GOOGLE_SERVICE_ACCOUNT_JSON",
                "GOOGLE_SHEET_ID", "SMTP_PASS", "SMTP_USER", "IMAP_HOST")

def main():
    print("ENIX Lightning AI — offline smoke test")
    print("Python:", sys.version.split()[0])
    print("Repository:", ROOT.name)
    for name in SAFE_KEYS:
        value = os.environ.get(name, "").lower()
        print(name + ":", "DISABLED" if value != "true" else "ENABLED (not used in this offline test)")
    for name in PRIVATE_KEYS:
        print(name + ":", "configured" if os.environ.get(name) else "not configured")
    print("Running mocked discovery / email tests; NO outbound network or email calls.")
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "cloud"),
         "-p", "test_*.py", "-v"], cwd=ROOT, check=False)
    if result.returncode:
        print("FAIL: do not enable scheduling, discovery, or sending.")
        raise SystemExit(result.returncode)
    print("PASS: offline cloud runtime is operational; no real leads/emails involved.")

if __name__ == "__main__":
    main()
