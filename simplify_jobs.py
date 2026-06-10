#!/usr/bin/env python3
"""simplify_jobs.py - new-grad/early-career discovery via the SimplifyJobs list.

The SimplifyJobs "New-Grad-Positions" GitHub repo is the highest-signal source for
new-grad SWE roles: continuously community-updated, each listing links DIRECTLY to the
company's ATS posting (Greenhouse/Lever/Workday/etc.), and dead roles are flagged
inactive. This pulls its machine-readable listings JSON and filters by state/remote +
keyword, in the style of amazon_jobs.py / google_careers.py.

Listings here are DISCOVERY (aggregator), not company-surface verification: a kept role
still needs SKILL.md Phase 4 (verify the ATS URL live + pull the authoritative location)
before being tiered - the direct ATS url makes that one fetch.

Usage:
    python simplify_jobs.py --state CO                  # CO + US-remote new-grad roles
    python simplify_jobs.py "machine learning" --state CO --days 30
    python simplify_jobs.py --state CO --no-remote --json
"""
import argparse
import datetime
import json
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
LISTINGS_URL = ("https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/"
                "dev/.github/scripts/listings.json")

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}


def fetch_listings(timeout=30):
    req = urllib.request.Request(LISTINGS_URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def loc_verdict(locations, state, include_remote):
    """'state' when any location is in the target state; 'remote' for US-remote
    listings; None otherwise. 'Remote in USA' / bare 'Remote' both count as US-remote
    (the list is US-centric), but the ATS posting must still confirm it (Phase 4c)."""
    name = STATE_NAMES.get(state, "")
    for loc in locations or []:
        if state and (loc.strip().endswith(f", {state}") or name and name in loc):
            return "state"
    if include_remote:
        for loc in locations or []:
            low = loc.lower().strip()
            # "Remote in UK"/"Remote in Canada" must NOT pass (the foreign-remote
            # false-match from SKILL.md): require an explicit US token or bare "Remote".
            if low.startswith("remote") and (
                    "usa" in low or "united states" in low or low == "remote"):
                return "remote"
    return None


def iso(unix_ts):
    try:
        return datetime.date.fromtimestamp(int(unix_ts)).isoformat()
    except (TypeError, ValueError, OSError):
        return None


def main():
    ap = argparse.ArgumentParser(
        description="New-grad role discovery from the SimplifyJobs list (aggregator - "
                    "verify each kept role on its ATS URL per SKILL.md Phase 4).")
    ap.add_argument("query", nargs="?", default="",
                    help="Optional keyword filter on the title (e.g. 'machine learning')")
    ap.add_argument("--state", default="CO", help="2-letter state (default CO)")
    ap.add_argument("--no-remote", action="store_true",
                    help="Exclude US-remote listings (state matches only)")
    ap.add_argument("--days", type=int,
                    help="Only listings posted/updated in the last N days")
    ap.add_argument("--category", default="",
                    help="Filter on Simplify category, e.g. 'Software', 'Data'")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    state = (a.state or "").upper()
    data = fetch_listings()
    cutoff = None
    if a.days:
        cutoff = (datetime.date.today() - datetime.timedelta(days=a.days)).isoformat()

    rows = []
    for d in data:
        if not (d.get("active") and d.get("is_visible")):
            continue
        verdict = loc_verdict(d.get("locations"), state, not a.no_remote)
        if verdict is None:
            continue
        if a.query and a.query.lower() not in (d.get("title") or "").lower():
            continue
        if a.category and a.category.lower() not in (d.get("category") or "").lower():
            continue
        posted = iso(d.get("date_posted")) or iso(d.get("date_updated"))
        if cutoff and (posted or "0000") < cutoff:
            continue
        rows.append({
            "company": d.get("company_name"),
            "title": d.get("title"),
            "locations": d.get("locations"),
            "loc_match": verdict,
            "category": d.get("category"),
            "sponsorship": d.get("sponsorship"),
            "posted": posted,
            "url": d.get("url"),
        })
    rows.sort(key=lambda r: r["posted"] or "", reverse=True)

    if a.json:
        print(json.dumps(rows, indent=2))
        return
    scope = f"{state} {'(+US remote)' if not a.no_remote else '(state only)'}"
    print(f"{len(rows)} active new-grad listing(s) for {scope}"
          + (f", title~'{a.query}'" if a.query else "")
          + (f", last {a.days}d" if a.days else "") + ":\n")
    for r in rows:
        locs = "; ".join(r["locations"] or [])
        print(f"  [{r['loc_match']:>6}] {r['company']}: {r['title']}")
        print(f"           {locs}  ·  posted {r['posted'] or '?'}  ·  {r['category']}"
              + (f"  ·  {r['sponsorship']}" if r.get("sponsorship") else ""))
        print(f"           {r['url']}")
    if rows:
        print("\nNOTE: aggregator discovery - verify each role live + location on its "
              "ATS URL (Phase 4) before tiering; many urls are direct ATS links.")


if __name__ == "__main__":
    main()
