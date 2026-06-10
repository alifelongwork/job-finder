#!/usr/bin/env python3
"""usajobs.py - federal civilian roles via the official USAJOBS Search API.

Covers the federal blind spot: NIST Boulder (one of the largest quantum employers in
Colorado), NOAA Boulder, NREL-adjacent federal labs, and every other agency posting on
USAJOBS.gov. Federal roles carry a citizenship gate (US citizens only - which this
project's candidates can individually meet or not; check the candidate record) and slow
timelines, but entry-level GS roles are real pipeline for early-career candidates.

SETUP (one-time, free, ~2 minutes):
  1. Request an API key at https://developer.usajobs.gov/apirequest/ (email + instant key)
  2. Set environment variables (PowerShell):
       $env:USAJOBS_API_KEY = "<your key>"
       $env:USAJOBS_EMAIL   = "<the email you registered>"
     (persist with setx, or add to your PowerShell profile)

Presence in this API = live posting on USAJOBS (it is the authoritative federal source,
satisfies Phase 4c/4d); PositionLocation is authoritative. Roles close on a hard
ApplicationCloseDate - surface it.

Usage:
    python usajobs.py "computer science" --location Colorado
    python usajobs.py "software" --location Colorado --remote --json
    python usajobs.py "quantum" --org "National Institute of Standards and Technology"
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "https://data.usajobs.gov/api/search"


def credentials():
    key = os.environ.get("USAJOBS_API_KEY")
    email = os.environ.get("USAJOBS_EMAIL")
    if not key or not email:
        sys.exit(
            "USAJOBS credentials missing.\n"
            "  1. Get a free key (instant): https://developer.usajobs.gov/apirequest/\n"
            "  2. Set:  $env:USAJOBS_API_KEY = \"<key>\"\n"
            "           $env:USAJOBS_EMAIL   = \"<registered email>\"\n"
            "Then re-run this command.")
    return key, email


def fetch(params, key, email, timeout=30):
    url = f"{BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "Host": "data.usajobs.gov",
        "User-Agent": email,
        "Authorization-Key": key,
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def parse_items(payload):
    items = (((payload.get("SearchResult") or {}).get("SearchResultItems")) or [])
    rows = []
    for it in items:
        d = (it or {}).get("MatchedObjectDescriptor") or {}
        locs = "; ".join(l.get("LocationName", "") for l in d.get("PositionLocation") or [])
        pay = (d.get("PositionRemuneration") or [{}])[0]
        try:
            lo = int(float(pay.get("MinimumRange", 0)))
            hi = int(float(pay.get("MaximumRange", 0)))
        except (TypeError, ValueError):
            lo = hi = 0
        interval = pay.get("RateIntervalCode", "")
        grade = ""
        jg = d.get("JobGrade") or []
        ur = (d.get("UserArea") or {}).get("Details") or {}
        if jg:
            grade = f"{jg[0].get('Code','')}-{ur.get('LowGrade','')}/{ur.get('HighGrade','')}"
        rows.append({
            "title": d.get("PositionTitle"),
            "org": d.get("OrganizationName"),
            "dept": d.get("DepartmentName"),
            "locations": locs,
            "grade": grade,
            "comp_min": lo if interval == "Per Year" else None,
            "comp_max": hi if interval == "Per Year" else None,
            "posted": (d.get("PublicationStartDate") or "")[:10] or None,
            "closes": (d.get("ApplicationCloseDate") or "")[:10] or None,
            "url": d.get("PositionURI"),
        })
    total = ((payload.get("SearchResult") or {}).get("SearchResultCountAll"))
    return rows, total


def main():
    ap = argparse.ArgumentParser(
        description="Federal roles via the USAJOBS API (citizenship gate applies).")
    ap.add_argument("keyword", nargs="?", default="software")
    ap.add_argument("--location", default="Colorado",
                    help="LocationName filter, e.g. 'Colorado' or 'Boulder, Colorado'")
    ap.add_argument("--remote", action="store_true", help="Remote-eligible roles only")
    ap.add_argument("--org", help="Organization filter, e.g. 'National Institute of "
                                  "Standards and Technology'")
    ap.add_argument("--limit", type=int, default=100, help="Results per page (max 500)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    key, email = credentials()
    params = {"Keyword": a.keyword, "ResultsPerPage": min(a.limit, 500)}
    if a.remote:
        params["RemoteIndicator"] = "True"
    elif a.location:
        params["LocationName"] = a.location
    if a.org:
        params["Organization"] = a.org

    payload = fetch(params, key, email)
    rows, total = parse_items(payload)

    if a.json:
        print(json.dumps(rows, indent=2))
        return
    scope = "remote-eligible" if a.remote else a.location
    print(f"{len(rows)} of {total} live USAJOBS posting(s) for '{a.keyword}' ({scope}):\n")
    for r in rows:
        comp = (f"  ·  ${r['comp_min']:,}-${r['comp_max']:,}/yr"
                if r["comp_min"] else "")
        print(f"  {r['org']}: {r['title']}  [{r['grade']}]")
        print(f"      {r['locations']}{comp}")
        print(f"      posted {r['posted'] or '?'}  ·  CLOSES {r['closes'] or '?'}  ·  {r['url']}")
    if rows:
        print("\nNOTE: federal = US-citizen gate; applications close HARD on the closes "
              "date; tag stored roles dedup_key usajobs:<agency>:<control#>.")


if __name__ == "__main__":
    main()
