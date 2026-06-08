#!/usr/bin/env python3
"""Verify Amazon roles from the public amazon.jobs search API (custom, non-ATS).

Amazon runs no Greenhouse/Lever/Workday feed; its careers site is backed by a public
JSON endpoint: https://www.amazon.jobs/en/search.json . The endpoint only honors
`base_query` + `country` server-side (loc_query/state are IGNORED — request echo shows
location:null), so we paginate (offset) and filter by state CLIENT-SIDE on each job's
`state` field. A role present in this feed is LIVE on the company surface (Phase 4c/4d);
its `state`/`city` are the authoritative location.

Usage:
    python amazon_jobs.py "software engineer" --state CO
    python amazon_jobs.py "software developer" --state CO --json --max-pages 12
"""
import argparse, json, sys, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
BASE = "https://www.amazon.jobs/en/search.json"
HOST = "https://www.amazon.jobs"
PAGE = 100  # amazon.jobs `state` field is the 2-letter code (CO, WA, ...)


def fetch_page(query, offset):
    qs = urllib.parse.urlencode({"base_query": query, "country": "USA",
                                 "result_limit": PAGE, "offset": offset, "sort": "recent"})
    req = urllib.request.Request(f"{BASE}?{qs}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def level_tag(job):
    title = (job.get("title") or "").lower()
    if job.get("is_intern"):
        return "intern"
    if job.get("university_job"):
        return "new-grad"
    if any(k in title for k in (" iii", " principal", " senior", " sr ", " staff")):
        return "senior"
    if " ii" in title:
        return "L5/II"
    return "entry/mid"


def parse(query, state, max_pages):
    rows, total, capped = [], None, False
    for i in range(max_pages):
        d = fetch_page(query, i * PAGE)
        total = d.get("hits", total)
        jobs = d.get("jobs", [])
        if not jobs:
            break
        for j in jobs:
            if state and (j.get("state") or "").upper() != state:
                continue
            rows.append({
                "id": j.get("id_icims"),
                "title": j.get("title"),
                "level": level_tag(j),
                "location": j.get("normalized_location") or f"{j.get('city')}, {j.get('state')}",
                "posted": j.get("posted_date"),
                "url": HOST + (j.get("job_path") or ""),
            })
        if total and (i + 1) * PAGE < total:
            capped = (i == max_pages - 1)
        else:
            break
    return rows, total, capped


def main():
    ap = argparse.ArgumentParser(description="Verify Amazon roles (live + location) via amazon.jobs API.")
    ap.add_argument("query", nargs="?", default="software engineer")
    ap.add_argument("--state", default="CO", help="2-letter state filter (default CO); blank for all US")
    ap.add_argument("--max-pages", type=int, default=12, help=f"pages of {PAGE} to scan (default 12)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    state = a.state.upper() if a.state else None
    rows, total, capped = parse(a.query, state, a.max_pages)
    if a.json:
        print(json.dumps(rows, indent=2))
        return
    scope = f" in {a.state.upper()}" if a.state else ""
    print(f"{len(rows)} live '{a.query}' role(s){scope} on amazon.jobs "
          f"(scanned up to {a.max_pages*PAGE} of {total} US hits"
          f"{'; CAPPED — raise --max-pages' if capped else ''}):\n")
    for r in rows:
        print(f"  [{r['level']:>9}] {r['title']}")
        print(f"             {r['location']}  ·  posted {r['posted']}")
        print(f"             {r['url']}")
    if not rows:
        print("  (none — Amazon has no matching roles in that state right now)")


if __name__ == "__main__":
    main()
