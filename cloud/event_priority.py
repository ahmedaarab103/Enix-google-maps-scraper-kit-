"""Evidence-based prioritization of event photography / videography opportunities.

Google Maps identifies event organizers, not the dates of their upcoming events.
Do not claim a photography vacancy unless the organizer has published an actual
request for photo/video providers. Events with unverified dates stay RESEARCH.

This module performs no network activity and NEVER sends email.
"""
from datetime import date, datetime
from urllib.parse import urlparse

PRIORITY_ORDER = ("P1", "P2", "P3", "FUTURE", "EXPIRED", "RESEARCH")


def _has_evidence_link(value):
    try:
        parsed = urlparse(str(value or "").strip())
        return parsed.scheme in ("https", "http") and bool(parsed.hostname)
    except ValueError:
        return False


def prioritize(event_date, event_source_url, coverage_need="UNKNOWN",
               coverage_need_source_url="", *, today=None):
    """Return a priority and honest reason.

    Valid date and source are required. OPEN_BRIEF additionally requires
    independent evidence linked in coverage_need_source_url. Merely announcing
    an event does not imply its organizers need a photographer.
    """
    today = today or date.today()
    if not event_date or not _has_evidence_link(event_source_url):
        return "RESEARCH", "Upcoming event date and credible source not verified"
    try:
        day = date.fromisoformat(str(event_date).strip())
    except (TypeError, ValueError):
        return "RESEARCH", "Invalid event date; verify YYYY-MM-DD"
    delta = (day-today).days
    if delta < 0:
        return "EXPIRED", "Event date has passed"
    requested = (str(coverage_need or "").strip().upper() == "OPEN_BRIEF"
                 and _has_evidence_link(coverage_need_source_url))
    if requested and delta <= 21:
        return "P1", f"Published photo/video supplier need; event in {delta} days"
    if requested and delta <= 45:
        return "P2", f"Published photo/video supplier need; event in {delta} days"
    if delta <= 45:
        return "P2", f"Verified event in {delta} days; coverage need UNKNOWN"
    if delta <= 90:
        return "P3", f"Verified event in {delta} days; coverage need UNKNOWN"
    return "FUTURE", f"Verified event in {delta} days; research later"


def classify_row(row, *, today=None):
    if not str(row.get("event_title", "")).strip():
        return "RESEARCH", "Named event not yet verified"
    return prioritize(row.get("event_date", ""), row.get("event_source_url",""),
                      row.get("coverage_need","UNKNOWN"),
                      row.get("coverage_need_source_url",""),today=today)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Offline event opportunity prioritization.")
    parser.add_argument("--date", default="")
    parser.add_argument("--event-url", default="")
    parser.add_argument("--need", default="UNKNOWN", choices=["UNKNOWN","OPEN_BRIEF"])
    parser.add_argument("--need-url", default="")
    a = parser.parse_args()
    priority, why = prioritize(a.date, a.event_url, a.need, a.need_url)
    print(priority, "-", why)
