#!/usr/bin/env python3
"""Verify Google careers roles from the embedded AF_initDataCallback data.

Google's careers board (google.com/about/careers/applications) is JS-rendered and its
legacy JSON API (careers.google.com/api/v3) is DEAD (404). But the results page
server-embeds the full job data in an `AF_initDataCallback({key:'ds:1', data:[...]})`
block. This parses that block — no browser, stdlib only.

Field map inside each job record (data[0][i]):
    [0]      job id            (URL: .../jobs/results/<id>-<title-slug>)
    [1]      title
    [4][1]   minimum-qualifications HTML (degree level lives here)
    [9]      list of locations; each loc: [0]=display, [2]=city, [4]=state code

Usage:
    python google_careers.py quantum --state CO
    python google_careers.py "software engineer" --state CO --json
A role present in this feed is LIVE on the company surface (satisfies Phase 4c/4d).
"""
import argparse, json, re, sys, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
BASE = "https://www.google.com/about/careers/applications/jobs/results/"


def fetch(query):
    url = BASE + "?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def extract_jobs(html):
    """Return the list of job records from the ds:1 AF_initDataCallback block."""
    m = re.search(r"AF_initDataCallback\((\{key:\s*'ds:1'.*?\})\);", html, re.DOTALL)
    if not m:
        return []
    dm = re.search(r"data:\s*(\[.*\]),\s*sideChannel", m.group(1), re.DOTALL)
    data = json.loads(dm.group(1))
    # The job list is the top-level entry that is a list of records carrying a
    # title string at [1]; don't hard-code data[0] in case the layout shifts.
    for entry in data:
        if (isinstance(entry, list) and entry and isinstance(entry[0], list)
                and len(entry[0]) > 1 and isinstance(entry[0][1], str)):
            return entry
    return []


def degree_level(job):
    """Coarse level signal from the minimum-qualifications HTML."""
    try:
        quals = job[4][1].lower()
    except (IndexError, TypeError):
        return "?"
    if "phd" in quals:
        return "PhD"
    if "master" in quals or "ms degree" in quals:
        return "MS"
    if "bachelor" in quals or "bs degree" in quals:
        return "BS"
    return "?"


def locations(job):
    out = []
    try:
        for L in job[9] or []:
            disp = L[0] if len(L) > 0 else "?"
            state = L[4] if len(L) > 4 else ""
            out.append({"display": disp, "state": state})
    except (IndexError, TypeError):
        pass
    return out


def parse(html, state=None):
    rows = []
    for job in extract_jobs(html):
        locs = locations(job)
        if state and not any(l["state"] == state for l in locs):
            continue
        rows.append({
            "id": job[0],
            "title": job[1],
            "level": degree_level(job),
            "locations": [l["display"] for l in locs],
            "url": f"{BASE}{job[0]}",
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description="Verify Google careers roles (live + location).")
    ap.add_argument("query", nargs="?", default="quantum")
    ap.add_argument("--state", help="2-letter state filter, e.g. CO")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    a = ap.parse_args()
    rows = parse(fetch(a.query), a.state)
    if a.json:
        print(json.dumps(rows, indent=2))
        return
    scope = f" in {a.state}" if a.state else ""
    print(f"{len(rows)} live '{a.query}' role(s){scope} on Google careers:\n")
    for r in rows:
        print(f"  [{r['level']:>3}] {r['title']}")
        print(f"        {', '.join(r['locations'])}")
        print(f"        {r['url']}")


if __name__ == "__main__":
    main()
