#!/usr/bin/env python3
"""ats_probe.py — resolve a company's ATS hiring feed (company-level verification helper).

The company-level analog of confirming a single job is live. Given a company name, this
tries the known public ATS JSON feeds (Greenhouse, Lever US+EU, Ashby, Workable, Rippling,
SmartRecruiters, BambooHR, Recruitee; Workday is opt-in) for a set of candidate slugs and
reports which platform/slug resolved,
how many open roles it lists, and a few sample titles/locations. Stdlib only (urllib) —
modeled on google_careers.py. It NEVER writes the database: run it, eyeball the result,
then record the outcome with `python jobsdb.py company verify ...` (this prints a
ready-to-paste command).

Slugs are GUESSES derived from the name unless you pass --slug. A wrong guess can resolve
to a DIFFERENT company's real board, so the sample company/titles are printed for you to
sanity-check before trusting a hit.

Usage:
    python ats_probe.py "Acme Robotics"
    python ats_probe.py "Acme Robotics" --slug acmerobotics --slug acme-robotics
    python ats_probe.py "Acme Robotics" --platform greenhouse --json
    python ats_probe.py "Big Enterprise" --workday-tenant bigco --workday-site Careers --workday-n 5

Result vocabulary (maps to `company verify --status`):
    hit   -> a feed resolved (count>0 => feed_verified; count==0 => feed exists, no open roles)
    miss  -> clean 404; the slug is not on that ATS
    error -> timeout / 5xx / unreachable / non-JSON => INCONCLUSIVE, record `unresolved`, retry
"""
import argparse
import json
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

# Make stdout UTF-8 so unicode in job titles/locations (and em-dashes here) print on
# Windows consoles (cp1252) instead of raising/mangling — same guard as jobsdb.py.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
DEFAULT_TIMEOUT = 15
# Corporate suffixes stripped before deriving slugs (so "Acme Labs, Inc." -> "acme").
CORP_SUFFIXES = {"inc", "llc", "ltd", "corp", "co", "company", "labs", "lab", "ai",
                 "technologies", "technology", "systems", "group", "holdings"}


# ---------------------------------------------------------------------------
# slug derivation
# ---------------------------------------------------------------------------
def candidate_slugs(name):
    """Order-preserving, de-duped guesses for a company's ATS slug from its display name.

    'Acme Robotics, Inc.' -> ['acmerobotics', 'acme-robotics', 'acme']
    """
    cleaned = "".join(c if (c.isalnum() or c.isspace()) else " " for c in (name or ""))
    tokens = [t for t in cleaned.lower().split() if t]
    while len(tokens) > 1 and tokens[-1] in CORP_SUFFIXES:
        tokens.pop()
    out = []
    for s in ("".join(tokens), "-".join(tokens), tokens[0] if tokens else ""):
        if s and s not in out:
            out.append(s)
    return out


# ---------------------------------------------------------------------------
# transport — never raises; returns (result, http_code, payload, error_msg)
# result is one of: "ok" (got JSON), "miss" (404), "error" (anything else)
# ---------------------------------------------------------------------------
def _request(url, timeout, *, data=None, headers=None):
    hdrs = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs,
                                 method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
        try:
            return ("ok", 200, json.loads(body), None)
        except (json.JSONDecodeError, ValueError):
            return ("error", 200, None, "non-JSON response")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return ("miss", 404, None, None)
        return ("error", e.code, None, f"HTTP {e.code}")
    except (urllib.error.URLError, socket.timeout) as e:
        return ("error", None, None, str(getattr(e, "reason", e)) or "unreachable")
    except Exception as e:  # belt-and-suspenders: a probe must never crash the caller
        return ("error", None, None, str(e))


# ---------------------------------------------------------------------------
# per-platform normalizers: raw JSON -> {"count": int, "samples": [{title,location,url}]}
# each is defensive — malformed/empty payloads yield count 0, never raise.
# ---------------------------------------------------------------------------
def _samples(items, title_keys, loc_fn, url_keys):
    out = []
    for it in (items or [])[:3]:
        if not isinstance(it, dict):
            continue
        title = next((it.get(k) for k in title_keys if it.get(k)), "?")
        url = next((it.get(k) for k in url_keys if it.get(k)), "")
        try:
            loc = loc_fn(it) or "?"
        except (KeyError, TypeError, IndexError):
            loc = "?"
        out.append({"title": title, "location": loc, "url": url})
    return out


def parse_greenhouse(j):
    jobs = j.get("jobs", []) if isinstance(j, dict) else []
    return {"count": len(jobs),
            "samples": _samples(jobs, ("title",),
                                lambda it: (it.get("location") or {}).get("name"),
                                ("absolute_url",))}


def parse_lever(j):
    jobs = j if isinstance(j, list) else []
    return {"count": len(jobs),
            "samples": _samples(jobs, ("text",),
                                lambda it: (it.get("categories") or {}).get("location"),
                                ("hostedUrl", "applyUrl"))}


def parse_ashby(j):
    jobs = j.get("jobs", []) if isinstance(j, dict) else []
    return {"count": len(jobs),
            "samples": _samples(jobs, ("title",),
                                lambda it: it.get("location"),
                                ("jobUrl", "applyUrl"))}


def parse_workable(j):
    jobs = j.get("jobs", []) if isinstance(j, dict) else []
    def loc(it):
        return it.get("location") or ", ".join(
            x for x in (it.get("city"), it.get("state"), it.get("country")) if x)
    return {"count": len(jobs),
            "samples": _samples(jobs, ("title",), loc, ("shortlink", "url", "application_url"))}


def parse_rippling(j):
    jobs = j if isinstance(j, list) else (j.get("jobs", []) if isinstance(j, dict) else [])
    def loc(it):
        w = it.get("workLocation") or it.get("location") or {}
        if isinstance(w, dict):
            return w.get("label") or w.get("name")
        return w if isinstance(w, str) else None
    return {"count": len(jobs),
            "samples": _samples(jobs, ("name", "title"), loc, ("url", "jobUrl"))}


def parse_smartrecruiters(j):
    jobs = j.get("content", []) if isinstance(j, dict) else []
    total = j.get("totalFound") if isinstance(j, dict) else None
    def loc(it):
        l = it.get("location") or {}
        return ", ".join(x for x in (l.get("city"), l.get("region"), l.get("country")) if x)
    return {"count": total if isinstance(total, int) else len(jobs),
            "samples": _samples(jobs, ("name",), loc, ("ref",))}


def parse_bamboohr(j):
    jobs = j.get("result", []) if isinstance(j, dict) else []
    def loc(it):
        l = it.get("location") or {}
        if isinstance(l, dict):
            base = ", ".join(x for x in (l.get("city"), l.get("state")) if x)
        else:
            base = str(l or "")
        return (base + (" (remote)" if it.get("isRemote") else "")) or None
    return {"count": len(jobs),
            "samples": _samples(jobs, ("jobOpeningName", "title"), loc, ("url",))}


def parse_recruitee(j):
    jobs = j.get("offers", []) if isinstance(j, dict) else []
    return {"count": len(jobs),
            "samples": _samples(jobs, ("title",),
                                lambda it: it.get("location") or ", ".join(
                                    x for x in (it.get("city"), it.get("country")) if x),
                                ("careers_url", "url"))}


def parse_workday(j):
    posts = j.get("jobPostings", []) if isinstance(j, dict) else []
    total = j.get("total") if isinstance(j, dict) else None
    return {"count": total if isinstance(total, int) else len(posts),
            "samples": _samples(posts, ("title",),
                                lambda it: it.get("locationsText"),
                                ("externalPath",))}


# name, URL template (slug -> url), parser. Lever EU is a fallback for Lever US.
PLATFORMS = [
    ("greenhouse", "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", parse_greenhouse),
    ("lever",      "https://api.lever.co/v0/postings/{slug}?mode=json",       parse_lever),
    ("lever-eu",   "https://api.eu.lever.co/v0/postings/{slug}?mode=json",    parse_lever),
    ("ashby",      "https://api.ashbyhq.com/posting-api/job-board/{slug}",    parse_ashby),
    ("workable",   "https://apply.workable.com/api/v1/widget/accounts/{slug}", parse_workable),
    ("rippling",   "https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs", parse_rippling),
    ("smartrecruiters", "https://api.smartrecruiters.com/v1/companies/{slug}/postings",
     parse_smartrecruiters),
    ("bamboohr",   "https://{slug}.bamboohr.com/careers/list",                parse_bamboohr),
    ("recruitee",  "https://{slug}.recruitee.com/api/offers/",                parse_recruitee),
]


# Platforms where the slug is the HOSTNAME: an unresolvable domain there is a clean
# miss (the company isn't on that ATS), not an inconclusive network error.
HOST_BASED = {"bamboohr", "recruitee"}
_DNS_FAIL = ("getaddrinfo", "name or service", "nodename", "no address")


def probe_slug(slug, timeout, only=None):
    """Try each platform feed for one slug. Returns a list of attempt dicts."""
    attempts = []
    lever_hit = False
    for name, tmpl, parse in PLATFORMS:
        if only and not name.startswith(only):
            continue
        if name == "lever-eu" and lever_hit:
            continue  # US Lever already resolved; skip the EU fallback
        url = tmpl.format(slug=urllib.parse.quote(slug, safe=""))
        result, code, payload, err = _request(url, timeout)
        if (result == "error" and name in HOST_BASED
                and any(s in (err or "").lower() for s in _DNS_FAIL)):
            result, err = "miss", None
        att = {"platform": name, "slug": slug, "url": url,
               "result": "hit" if result == "ok" else result,
               "http": code, "count": 0, "samples": [], "error": err}
        if result == "ok" and name == "smartrecruiters":
            # SmartRecruiters answers 200 + totalFound:0 for ANY name (verified
            # 2026-06-10), so an empty result proves nothing — treat as a miss.
            # (Cost: a real SR company with temporarily 0 postings reads as a miss.)
            norm = parse(payload)
            if norm["count"] == 0:
                att["result"] = "miss"
                attempts.append(att)
                continue
        if result == "ok":
            norm = parse(payload)
            att["count"], att["samples"] = norm["count"], norm["samples"]
            if name == "lever":
                lever_hit = True
        attempts.append(att)
    return attempts


def probe_workday(name, tenant, site, wd_n, timeout):
    host = f"https://{tenant}.wd{wd_n}.myworkdayjobs.com"
    url = f"{host}/wday/cxs/{tenant}/{site}/jobs"
    body = json.dumps({"limit": 20, "offset": 0, "searchText": "",
                       "appliedFacets": {}}).encode("utf-8")
    result, code, payload, err = _request(
        url, timeout, data=body, headers={"Content-Type": "application/json"})
    att = {"platform": "workday", "slug": f"{tenant}/{site}", "url": url,
           "result": "hit" if result == "ok" else result,
           "http": code, "count": 0, "samples": [], "error": err}
    if result == "ok":
        norm = parse_workday(payload)
        att["count"], att["samples"] = norm["count"], norm["samples"]
    return att


def probe(name, slugs, timeout, platform=None, workday=None):
    attempts = []
    for slug in slugs:
        attempts.extend(probe_slug(slug, timeout, only=platform))
    if workday:
        attempts.append(probe_workday(name, *workday, timeout))
    hits = [a for a in attempts if a["result"] == "hit"]
    # Prefer a hit with open roles; otherwise a resolved-but-empty feed.
    best = next((a for a in hits if a["count"] > 0), hits[0] if hits else None)
    return {"company": name, "attempts": attempts, "best": best}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _verify_hint(name, best):
    # A resolved feed is feed_verified even at 0 open roles — the slug/platform is confirmed.
    plat = best["platform"].replace("-eu", "")  # lever-eu records as platform 'lever'
    parts = [f'python jobsdb.py company verify "{name}"',
             "--status feed_verified", f"--ats-platform {plat}",
             f"--ats-slug {best['slug']}", f"--open-roles {best['count']}"]
    return "  " + " ".join(parts)


def main():
    ap = argparse.ArgumentParser(
        description="Resolve a company's ATS hiring feed (company-level verification).")
    ap.add_argument("name", help="Company display name (used to derive slugs + label)")
    ap.add_argument("--slug", action="append", dest="slugs",
                    help="Explicit ATS slug to try (repeatable; skips name-derived guesses)")
    ap.add_argument("--platform", help="Restrict to one ATS family, e.g. greenhouse / lever / ashby")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Per-request seconds")
    ap.add_argument("--json", action="store_true", help="Emit JSON")
    ap.add_argument("--workday-tenant", dest="wd_tenant", help="Workday tenant (opt-in; needs site+n)")
    ap.add_argument("--workday-site", dest="wd_site", help="Workday career-site name")
    ap.add_argument("--workday-n", dest="wd_n", help="Workday wdN data-center number, e.g. 5")
    a = ap.parse_args()

    wd = None
    if any((a.wd_tenant, a.wd_site, a.wd_n)):
        if not all((a.wd_tenant, a.wd_site, a.wd_n)):
            ap.error("Workday needs all three: --workday-tenant, --workday-site, --workday-n")
        wd = (a.wd_tenant, a.wd_site, a.wd_n)

    slugs = a.slugs or candidate_slugs(a.name)
    res = probe(a.name, slugs, a.timeout, platform=a.platform, workday=wd)

    if a.json:
        print(json.dumps(res, indent=2))
        return

    best = res["best"]
    print(f"Company: {a.name}   (slugs tried: {', '.join(slugs) or '-'})\n")
    for at in res["attempts"]:
        mark = {"hit": "OK ", "miss": "-- ", "error": "!! "}[at["result"]]
        tail = (f"{at['count']} role(s)" if at["result"] == "hit"
                else (at["error"] or "404"))
        print(f"  {mark}{at['platform']:<11} [{at['slug']}]  {tail}")
        for s in at["samples"]:
            print(f"        - {s['title']}  ({s['location']})")
    print()
    if best:
        print(f"RESOLVED on {best['platform']} (slug '{best['slug']}', "
              f"{best['count']} open role(s)). Record it:")
        print(_verify_hint(a.name, best))
    elif any(at["result"] == "error" for at in res["attempts"]):
        print("UNRESOLVED (some feeds errored — inconclusive, not a clean miss). "
              "Retry later or pass --slug; record as:")
        print(f'  python jobsdb.py company verify "{a.name}" --status unresolved')
    else:
        print("No public ATS feed found for these slugs (all clean 404s). The company may "
              "be on Workday/iCIMS/etc. or post only to LinkedIn — check its careers page, "
              "then record `--status careers_only` (page exists) or `--status unverified`.")


if __name__ == "__main__":
    main()
