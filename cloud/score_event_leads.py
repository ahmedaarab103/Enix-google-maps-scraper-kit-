"""Safe CRM-only event prioritization. No scraping or email sending.

Default is read-only: prints a count of rows requiring priority updates.
To write ONLY the priority cells, set ENIX_SCORE_APPLY_ENABLED=true and pass --apply.
Manual research must populate event_title, event_date, event_source_url;
coverage_need OPEN_BRIEF requires independently verified need_source_url.
"""
import argparse
import os

from discover_scraper import _open_book
from event_priority import classify_row


def refresh_priorities(book, apply=False):
    ws = book.worksheet("Leads")
    grid = ws.get_all_values()
    if not grid:
        raise RuntimeError("Missing CRM Leads headers")
    headers = [x.strip() for x in grid[0]]
    required = ("event_date", "event_source_url", "coverage_need",
                "coverage_need_source_url", "priority")
    if any(key not in headers for key in required):
        raise RuntimeError("CRM missing event-priority columns")
    idx = {key: headers.index(key) for key in headers}
    reviewed, updates = 0, 0
    counts = {}
    for row_idx, values in enumerate(grid[1:], start=2):
        row = {key: values[col].strip() if col < len(values) else ""
               for key, col in idx.items()}
        if not row.get("company",""):
            continue
        reviewed += 1
        priority, reason = classify_row(row)
        counts[priority] = counts.get(priority,0)+1
        if row.get("priority","") != priority:
            updates += 1
            if apply:
                ws.update_cell(row_idx, idx["priority"]+1, priority)
    return {"reviewed":reviewed,"priority_updates":updates,"counts":counts,"applied":apply}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Update ONLY priority column")
    args = parser.parse_args()
    if args.apply and os.getenv("ENIX_SCORE_APPLY_ENABLED","").lower() != "true":
        raise RuntimeError("Priority updates disabled; set ENIX_SCORE_APPLY_ENABLED=true")
    result = refresh_priorities(_open_book(),apply=args.apply)
    print("Event lead review:", result)


if __name__ == "__main__":
    main()
