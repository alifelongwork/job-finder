#!/usr/bin/env python3
"""discover.py - location-driven COMPANY discovery to bootstrap a fresh candidate's pipeline.

sweep.py re-checks roles at companies already in the DB; it never finds new COMPANIES. This
script is the other half: given a candidate's location + ranked categories, it harvests
location-scoped sources (job boards + company directories), extracts each unique employer and
any ATS apply-link they expose, confirms the company's hiring feed (reusing ats_probe), and
emits a company batch JSON for `jobsdb.py company verify-batch`. sweep.py then finds the roles.

Like sweep.py / ats_probe.py this NEVER writes the DB - it reads the candidate read-only and
writes a reviewable batch file plus a ready-to-paste next step.

Sources (each isolated: any failure -> 0 rows + a logged skip, never a crash):
  Stable     : simplify (SimplifyJobs JSON), usajobs (official API; US-citizen gate)
  Best-effort: builtin  (Built In <city>; no documented API -> degrades silently)
  Brittle    : linkedin, indeed, google (JS/anti-bot/ToS -> usually degrade to 0)
  Coverage   : seed (companies_seed/<region>__<sector>.json; agent-refreshed library)

Usage:
    python discover.py --candidate austin_long
    python discover.py --candidate austin_long --no-brittle --out company_scans/2026-06-25_discovery.json
    python discover.py --candidate austin_long --source simplify --source seed
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse
import urllib.request

import ats_probe
import sweep

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
SEED_DIR = os.path.join(HERE, "companies_seed")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
STABLE_SOURCES = ["simplify", "usajobs", "builtin", "seed"]
BRITTLE_SOURCES = ["linkedin", "indeed", "google"]
ALL_SOURCES = STABLE_SOURCES + BRITTLE_SOURCES
SEED_STALE_DAYS = 60


def log(msg):
    print(msg, file=sys.stderr)


def today():
    return datetime.date.today().isoformat()


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return s or "general"


def _get_json(url, timeout=20, data=None, headers=None):
    """GET/POST JSON with a browser UA. Returns parsed JSON or None on ANY failure
    (the silent-degrade contract every harvester relies on)."""
    hdr = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        hdr.update(headers)
    try:
        req = urllib.request.Request(url, data=data, headers=hdr)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# apply-link -> (platform, slug, careers_url)
# ---------------------------------------------------------------------------
# An aggregator that hands us the real board URL lets us skip slug-guessing entirely.
# The extracted slug is still UNCONFIRMED (links redirect / shorten), so callers feed it
# to the probe as a priority candidate rather than trusting it blindly.
def extract_platform_slug(apply_url):
    """Map an ATS posting URL to (platform, slug, careers_url), or (None, None, None)."""
    if not apply_url:
        return (None, None, None)
    try:
        u = urllib.parse.urlparse(apply_url)
    except ValueError:
        return (None, None, None)
    host = (u.netloc or "").lower()
    segs = [s for s in (u.path or "").split("/") if s]

    def seg0():
        return segs[0] if segs else None

    if "greenhouse.io" in host:
        slug = seg0()
        return ("greenhouse", slug, f"https://boards.greenhouse.io/{slug}") if slug else (None, None, None)
    if "lever.co" in host:
        slug = seg0()
        return ("lever", slug, f"https://jobs.lever.co/{slug}") if slug else (None, None, None)
    if "ashbyhq.com" in host:
        slug = seg0()
        return ("ashby", slug, f"https://jobs.ashbyhq.com/{slug}") if slug else (None, None, None)
    if "workable.com" in host:
        slug = seg0()
        return ("workable", slug, f"https://apply.workable.com/{slug}") if slug else (None, None, None)
    if "smartrecruiters.com" in host:
        slug = seg0()
        return ("smartrecruiters", slug, f"https://jobs.smartrecruiters.com/{slug}") if slug else (None, None, None)
    if "rippling.com" in host:
        slug = seg0()
        return ("rippling", slug, f"https://ats.rippling.com/{slug}/jobs") if slug else (None, None, None)
    if host.endswith("bamboohr.com"):
        slug = host.split(".")[0]
        return ("bamboohr", slug, f"https://{slug}.bamboohr.com/careers")
    if host.endswith("recruitee.com"):
        slug = host.split(".")[0]
        return ("recruitee", slug, f"https://{slug}.recruitee.com")
    m = sweep.WD_HOST_RE.search(apply_url)
    if m:
        tenant, wd_n = m.group(1), m.group(2)
        # site = first path segment that is not a locale like 'en-US'
        site = next((s for s in segs if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", s)), None)
        if site:
            host_base = f"https://{tenant}.wd{wd_n}.myworkdayjobs.com"
            return ("workday", f"{tenant}/{site}", f"{host_base}/{site}")
    return (None, None, None)


# ---------------------------------------------------------------------------
# location / category filtering (reuse sweep's matchers)
# ---------------------------------------------------------------------------
def loc_match(locations, states, allow_remote):
    """Best verdict ('state' | 'remote' | None) across a list of location strings."""
    best = None
    for loc in locations or []:
        v = sweep.location_verdict({"location": loc}, states, allow_remote)
        if v == "state":
            return "state"
        if v == "remote":
            best = "remote"
    return best


# ---------------------------------------------------------------------------
# harvesters: each returns rows {company, title, locations[], apply_url, source, kind}
#   kind 'job'  -> we observed a live role (category filter applies; evidence-floors status)
#   kind 'dir'  -> company directory/seed entry (no role title; skip category filter)
# Every harvester swallows its own errors and returns [] so one dead source never breaks a run.
# ---------------------------------------------------------------------------
def harvest_simplify(states, allow_remote, timeout):
    try:
        import simplify_jobs
        data = simplify_jobs.fetch_listings(timeout=timeout)
    except Exception:
        log("  [simplify] unavailable, skipped")
        return []
    rows = []
    for d in data or []:
        if not (d.get("active") and d.get("is_visible")):
            continue
        if loc_match(d.get("locations"), states, allow_remote) is None:
            continue
        rows.append({"company": d.get("company_name"), "title": d.get("title"),
                     "locations": d.get("locations") or [], "apply_url": d.get("url"),
                     "source": "simplify", "kind": "job"})
    log(f"  [simplify] {len(rows)} location-matched listing(s)")
    return rows


def harvest_usajobs(candidate, states, allow_remote, timeout):
    cz = (candidate.get("citizenship") or "").lower()
    if "citizen" not in cz:
        log("  [usajobs] skipped (federal roles need US citizenship)")
        return []
    key, email = os.environ.get("USAJOBS_API_KEY"), os.environ.get("USAJOBS_EMAIL")
    if not key or not email:
        log("  [usajobs] skipped (USAJOBS_API_KEY/USAJOBS_EMAIL not set)")
        return []
    try:
        import usajobs
        loc_name = states[0][1] if states else "United States"
        rows = []
        for _, _, kws in candidate.get("categories", []):
            kw = (kws or "").split(",")[0].strip() or "software"
            payload = usajobs.fetch({"Keyword": kw, "LocationName": loc_name,
                                     "ResultsPerPage": 100}, key, email, timeout)
            items, _ = usajobs.parse_items(payload)
            for it in items:
                rows.append({"company": it.get("org"), "title": it.get("title"),
                             "locations": [it.get("locations") or ""], "apply_url": it.get("url"),
                             "source": "usajobs", "kind": "job"})
        log(f"  [usajobs] {len(rows)} federal posting(s)")
        return rows
    except Exception:
        log("  [usajobs] unavailable, skipped")
        return []


def harvest_builtin(states, allow_remote, timeout):
    """Built In <city> has no documented public API (Next.js/Cloudflare). Best-effort: try a
    plausible JSON endpoint and degrade silently on block/non-JSON. Real coverage here is
    opportunistic; the agent seed pass is the dependable niche-coverage path."""
    city = states[0][1].lower().replace(" ", "") if states else None
    if not city:
        return []
    payload = _get_json(f"https://builtin{city}.com/api/search/jobs", timeout=timeout)
    if not isinstance(payload, dict):
        log("  [builtin] unavailable, skipped (no public JSON endpoint)")
        return []
    rows = []
    for j in (payload.get("jobs") or payload.get("results") or []):
        comp = (j.get("company") or {}).get("title") if isinstance(j.get("company"), dict) else j.get("company")
        rows.append({"company": comp, "title": j.get("title"),
                     "locations": [j.get("location") or ""],
                     "apply_url": j.get("applyUrl") or j.get("url"),
                     "source": "builtin", "kind": "job"})
    log(f"  [builtin] {len(rows)} listing(s)")
    return rows


def _brittle_stub(name):
    """LinkedIn/Indeed/Google Jobs are JS-rendered + anti-bot + ToS-gray. A stdlib scraper
    cannot reliably reach them, so these are isolated best-effort harvesters that log and
    return [] rather than fabricate. Wiring a real fetch path in later only touches this fn."""
    def harvest(states, allow_remote, timeout):
        log(f"  [{name}] skipped (no stdlib-reachable endpoint; agent-driven discovery instead)")
        return []
    return harvest


harvest_linkedin = _brittle_stub("linkedin")
harvest_indeed = _brittle_stub("indeed")
harvest_google = _brittle_stub("google")


def harvest_seed(region, sectors, timeout):
    """Read the accumulating seed library for (region x each sector). Returns (rows, gaps)
    where gaps are (region, sector) pairs with no fresh seed file -> the copilot fills them
    with an agent research pass, then re-runs --source seed."""
    rows, gaps = [], []
    region_key = slugify(region)
    for sector in sectors:
        path = os.path.join(SEED_DIR, f"{region_key}__{sector}.json")
        if not os.path.exists(path):
            gaps.append((region, sector))
            continue
        try:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        except Exception:
            gaps.append((region, sector))
            continue
        refreshed = doc.get("last_refreshed")
        if refreshed:
            age = (datetime.date.today() - datetime.date.fromisoformat(refreshed)).days
            if age > SEED_STALE_DAYS:
                gaps.append((region, sector))  # stale -> ask for a refresh, but still use it
        for e in doc.get("companies", []):
            hint = None
            if e.get("hint_platform") and e.get("hint_slug"):
                hint = (e["hint_platform"], e["hint_slug"], e.get("careers_url"))
            rows.append({"company": e.get("name"), "title": None, "locations": [],
                         "apply_url": e.get("careers_url"), "source": "seed", "kind": "dir",
                         "seed_hint": hint})
    log(f"  [seed] {len(rows)} company(ies) from library; {len(gaps)} gap(s)")
    return rows, gaps


# ---------------------------------------------------------------------------
# dedupe + confirm
# ---------------------------------------------------------------------------
def _canon(name):
    slugs = ats_probe.candidate_slugs(name)
    return slugs[0] if slugs else (name or "").lower()


def dedupe_companies(rows):
    """Collapse rows to unique companies keyed by canonical slug. Keeps the longest display
    name, the best apply-link hint, observed sample titles, and whether any row was a live
    role ('job')."""
    groups = {}
    for r in rows:
        name = (r.get("company") or "").strip()
        if not name:
            continue
        key = _canon(name)
        g = groups.setdefault(key, {"names": set(), "apply_urls": [], "samples": [],
                                     "sources": set(), "has_job": False, "seed_hint": None,
                                     "dir_careers": None})
        g["names"].add(name)
        g["sources"].add(r.get("source"))
        if r.get("apply_url"):
            g["apply_urls"].append(r["apply_url"])
        if r.get("title"):
            g["samples"].append(r["title"])
        if r.get("kind") == "job":
            g["has_job"] = True
        else:
            # directory/seed rows: apply_url IS a careers page (not a deep posting) -> usable
            # as the company's careers_url and as 'they hire' evidence even if no feed resolves.
            if r.get("apply_url") and not g["dir_careers"]:
                g["dir_careers"] = r["apply_url"]
        if r.get("seed_hint"):
            g["seed_hint"] = r["seed_hint"]
    out = []
    for key, g in groups.items():
        out.append({
            "key": key,
            "name": max(g["names"], key=len),
            "alt_names": sorted(n for n in g["names"] if n != max(g["names"], key=len)),
            "apply_urls": g["apply_urls"],
            "dir_careers": g["dir_careers"],
            "samples": g["samples"][:3],
            "sources": sorted(s for s in g["sources"] if s),
            "has_job": g["has_job"],
            "seed_hint": g["seed_hint"],
        })
    return out


def _status_from(best, attempts, has_evidence):
    """Map a probe outcome to a verification_status. A live observed role (has_evidence) or a
    known careers page floors a probe-miss at careers_only - we have proof they hire."""
    if best:
        return "feed_verified"
    had_error = any(a.get("result") == "error" for a in attempts)
    if had_error and not has_evidence:
        return "unresolved"
    return "careers_only" if has_evidence else "unverified"


def confirm_company(company, probe_timeout):
    """Resolve a company's feed. Prefer an apply-link-extracted (platform, slug); else fall
    back to ats_probe slug-guessing (flagged needs_review since a guess can collide)."""
    name = company["name"]
    hint = company.get("seed_hint")
    if not hint:
        for url in company.get("apply_urls", []):
            plat, slug, careers = extract_platform_slug(url)
            if plat and slug:
                hint = (plat, slug, careers)
                break
    guessed = False
    if hint and hint[0] and hint[1]:
        plat, slug, careers = hint
        if plat == "workday":
            m = sweep.WD_HOST_RE.search(careers or "")
            tenant, site = (slug.split("/", 1) + [""])[:2] if "/" in slug else (slug, "")
            wd_n = m.group(2) if m else "5"
            res = ats_probe.probe(name, [], probe_timeout, workday=(tenant, site, wd_n))
        else:
            res = ats_probe.probe(name, [slug], probe_timeout, platform=plat)
    else:
        guessed = True
        careers = None
        res = ats_probe.probe(name, ats_probe.candidate_slugs(name), probe_timeout)

    best, attempts = res.get("best"), res.get("attempts", [])
    # A known careers page (from a directory/seed entry) is both a fallback careers_url and
    # 'they hire' evidence: a company with a real careers page but no resolvable feed is
    # careers_only, not unresolved/unverified.
    known_careers = careers or company.get("dir_careers")
    has_evidence = company.get("has_job") or bool(known_careers)
    platform = slug_out = careers_out = open_roles = None
    note_bits = []

    # Only a feed from a TRUSTED source becomes authoritative: an apply-link we parsed or a
    # seed/DB hint (explicit platform+slug). A name-GUESSED slug that happens to hit some board
    # is too collision-prone (e.g. 'qc' -> a random Workable account, not QC Ware) - record it
    # as a lead in the note, never as the company's feed. needs_review surfaces it for a human.
    if best and not guessed:
        platform = best["platform"].replace("-eu", "")  # lever-eu records as lever
        slug_out, open_roles = best["slug"], best["count"]
        careers_out = careers or known_careers
        status = "feed_verified"
    elif best and guessed:
        note_bits.append(f"UNCONFIRMED guessed feed {best['platform']}:{best['slug']} "
                         f"({best['count']} roles) - verify with ats_probe before trusting")
        careers_out = known_careers
        status = "careers_only" if has_evidence else "unverified"
    elif hint:  # trusted platform/slug that didn't confirm live this run - keep slug, honest status
        platform, slug_out, careers_out = hint[0], hint[1], hint[2] or known_careers
        status = _status_from(best, attempts, has_evidence)
    else:
        careers_out = known_careers
        status = _status_from(best, attempts, has_evidence)

    if company.get("samples"):
        note_bits.append("roles seen: " + "; ".join(company["samples"]))
    if company.get("alt_names"):
        note_bits.append("aka " + ", ".join(company["alt_names"]))
    return {
        "name": name,
        "verification_status": status,
        "ats_platform": platform,
        "ats_slug": slug_out,
        "careers_url": careers_out,
        "open_roles": open_roles,
        "discovery_source": ",".join(company.get("sources", [])) or "discover",
        "needs_review": bool(guessed and best),  # guessed slug that hit -> eyeball the lead
        "note": " | ".join(note_bits) if note_bits else None,
    }


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------
def build_batch(candidate_slug, region, confirmed):
    return {
        "candidate": candidate_slug,
        "run_date": today(),
        "notes": f"discover.py draft - {region} + remote (review needs_review rows before verify-batch)",
        "companies": [{k: v for k, v in c.items() if v is not None or k in ("ats_platform", "ats_slug")}
                      for c in confirmed],
    }


def gather(candidate, states, region, sectors, sources, allow_remote, timeout):
    rows, gaps = [], []
    if "simplify" in sources:
        rows += harvest_simplify(states, allow_remote, timeout)
    if "usajobs" in sources:
        rows += harvest_usajobs(candidate, states, allow_remote, timeout)
    if "builtin" in sources:
        rows += harvest_builtin(states, allow_remote, timeout)
    if "linkedin" in sources:
        rows += harvest_linkedin(states, allow_remote, timeout)
    if "indeed" in sources:
        rows += harvest_indeed(states, allow_remote, timeout)
    if "google" in sources:
        rows += harvest_google(states, allow_remote, timeout)
    if "seed" in sources:
        seed_rows, gaps = harvest_seed(region, sectors, timeout)
        rows += seed_rows
    return rows, gaps


def filter_rows(rows, states, allow_remote, matcher):
    """Drop job rows that don't match a category; directory/seed rows pass (already scoped)."""
    kept = []
    for r in rows:
        if r.get("kind") == "job":
            if matcher((r.get("title") or "")) is None:
                continue
        kept.append(r)
    return kept


def main():
    ap = argparse.ArgumentParser(description="Location-driven company discovery (bootstrap).")
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--out", help="Write the company batch here (default: company_scans/<date>_discovery.json)")
    ap.add_argument("--source", action="append", dest="sources",
                    help="Restrict to specific source(s); repeatable. Default: all stable + brittle.")
    ap.add_argument("--no-brittle", action="store_true", help="Drop linkedin/indeed/google.")
    ap.add_argument("--no-remote", action="store_true", help="State matches only (exclude US-remote).")
    ap.add_argument("--max-companies", type=int, help="Cap unique companies confirmed (cost guard).")
    ap.add_argument("--timeout", type=int, default=20, help="Per-harvest HTTP timeout (s).")
    ap.add_argument("--probe-timeout", type=int, default=8, help="Per-platform probe timeout (s).")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    conn = sweep.connect_ro()
    candidate = sweep.load_candidate(conn, a.candidate)
    conn.close()

    states = sweep.constraint_states(candidate.get("location_constraint"))
    region = states[0][1] if states else "Remote"
    sectors = [slugify(label) for _, label, _ in candidate.get("categories", [])] or ["general"]
    allow_remote = not a.no_remote
    matcher = sweep.build_keyword_matcher(candidate.get("categories", []))

    sources = a.sources or (STABLE_SOURCES + ([] if a.no_brittle else BRITTLE_SOURCES))
    sources = [s for s in sources if s in ALL_SOURCES]

    if not a.quiet:
        log(f"Discovering companies for '{a.candidate}' in {region} "
            f"(remote {'on' if allow_remote else 'off'}); sources: {', '.join(sources)}")

    rows, gaps = gather(candidate, states, region, sectors, sources, allow_remote, a.timeout)
    rows = filter_rows(rows, states, allow_remote, matcher)
    companies = dedupe_companies(rows)
    if a.max_companies:
        companies = companies[: a.max_companies]

    if not a.quiet:
        log(f"Confirming feeds for {len(companies)} unique company(ies)...")
    confirmed = []
    seen_feed = {}  # (platform, slug) -> index, to merge companies that resolve to one feed
    for co in companies:
        rec = confirm_company(co, a.probe_timeout)
        feed_key = (rec["ats_platform"], rec["ats_slug"]) if rec["ats_slug"] else None
        if feed_key and feed_key in seen_feed:
            continue  # same confirmed feed as an earlier company -> already captured
        if feed_key:
            seen_feed[feed_key] = True
        confirmed.append(rec)

    batch = build_batch(a.candidate, region, confirmed)
    out = a.out or os.path.join("company_scans", f"{today()}_discovery.json")
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2)

    by_status = {}
    review = 0
    for c in confirmed:
        by_status[c["verification_status"]] = by_status.get(c["verification_status"], 0) + 1
        review += 1 if c.get("needs_review") else 0
    print(f"\n=== Discovery ({region}) ===")
    print(f"  unique companies: {len(confirmed)}  |  " +
          "  ".join(f"{k}: {v}" for k, v in sorted(by_status.items())))
    if review:
        print(f"  needs_review (guessed slug -> hit; eyeball before trusting): {review}")
    for region_name, sector in gaps:
        print(f"  GAP: no fresh seed for ({region_name} x {sector}). Run an agent research "
              f"pass to enumerate employers, write companies_seed/{slugify(region_name)}__{sector}.json, "
              f"then re-run: python discover.py --candidate {a.candidate} --source seed")
    print(f"\nDraft batch written: {out}")
    print(f"  Review needs_review rows, then:\n"
          f"    python jobsdb.py company verify-batch {out}")


if __name__ == "__main__":
    main()
