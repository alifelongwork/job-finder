#!/usr/bin/env python3
"""sweep.py - automated fresh-scan sweep over every feed-verified company.

Implements the "periodic fresh-scan sweep" from SKILL.md Phase 3a as a script instead
of agent prose. For one candidate it:

  1. reads the DB (READ-ONLY) for feed_verified companies + the candidate's stored
     constraints, ranked category keywords, seniority filter, and exclusions;
  2. fetches every company's public ATS JSON feed (Greenhouse, Lever US/EU, Ashby,
     Workable, Rippling, Workday CXS);
  3. filters fetched roles: over-level (title AND url slug), location (state tokens +
     the explicit-US-token rule for remote), category keywords, exclusions;
  4. diffs surviving roles against stored dedup_keys: NET-NEW roles go into a draft
     scan batch (verification_tag=verified, tier=null - the agent reviews, tiers, and
     then runs `jobsdb.py upsert-batch`); already-stored live roles seen in a feed are
     CONFIRMED live (presence in a fully-pulled feed = live);
  5. for stored live roles MISSING from their feed: complete feeds (Greenhouse/Lever/
     Ashby/Workable/Rippling return the whole list) => expiry candidates; Workday is
     paginated/cappable, so each missing Workday role is re-checked individually via
     the CXS job-detail GET (200=live, 404=gone) - never auto-expired on list absence.

This script NEVER writes the database. It prints ready-to-run `jobsdb.py mark` lines
and (with --out) writes a draft batch JSON for agent review. Stdlib only.

Encoded sweep lessons (see SKILL.md Phase 3a):
  - Workday CXS list: limit max 20, paginate by offset; big tenants fall back to
    per-keyword searchText sweeps; absence in a paginated feed is NOT proof of death.
  - Workday reqid: strip a trailing -N instance suffix EXCEPT for tenants whose reqid
    scheme makes it significant (UCAR REQ-YYYY-WK-N); see --keep-suffix-tenant.
  - Workday CXS `title` can drop seniority that IS in the externalPath slug - the
    over-level filter runs against the slug too.
  - Workable shortcodes are returned UPPERCASE; dedup keys are lowercased.
  - "Remote" only location-matches with an explicit US token (US/USA/United States).
  - A feed returning 0 vs erroring are different: HTTP status is logged per company
    so a dead feed reads as a blind spot, not an empty result.

Usage:
    python sweep.py --candidate austin_long
    python sweep.py --candidate austin_long --out job_scans/2026-06-10_sweep-draft.json
    python sweep.py --candidate austin_long --company Trimble --company IonQ
    python sweep.py --candidate austin_long --no-keyword-filter --report sweep_report.json
"""
import argparse
import datetime
import html
import json
import os
import re
import socket
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("JOBSDB_PATH", os.path.join(HERE, "jobs.db"))
DEFAULT_TIMEOUT = 20

# Over-level + non-FTE default filter (SKILL.md Phase 3a, extended). A candidate can
# override via the candidates.seniority_filter column (regex). Runs against the TITLE
# and the URL/externalPath slug (Workday hides seniority there).
DEFAULT_LEVEL_RE = (r"(?i)\b(senior|sr|staff|principal|lead|director|manager|architect|"
                    r"distinguished|fellow|chief|vp|iii|iv|postdoc(?:toral)?|"
                    r"intern(?:ship)?|co-?op)\b")

# Tokens too generic to count as a "distinctive" keyword hit on their own.
GENERIC_TOKENS = {"software", "engineer", "engineers", "engineering", "developer",
                  "developers", "scientist", "specialist", "analyst", "general"}

US_TOKEN_RE = re.compile(r"(?i)\b(US|USA|U\.S\.A?\.?|United States|America)\b")
REMOTE_RE = re.compile(r"(?i)\bremote\b")
HYBRID_RE = re.compile(r"(?i)\bhybrid\b")
AMBIGUOUS_LOC_RE = re.compile(r"(?i)^\s*\d+\s+locations?\s*$")  # Workday "2 Locations"

US_STATES = {
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


def today():
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# transport (modeled on ats_probe.py - never raises)
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
    except Exception as e:
        return ("error", None, None, str(e))


# ---------------------------------------------------------------------------
# comp parsing (best-effort; never guesses - None when not clearly an annual range)
# ---------------------------------------------------------------------------
_SALARY_RANGE_RE = re.compile(
    r"\$\s*(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d+)?\s*[kK])\s*"
    r"(?:-|–|—|to)\s*\$?\s*(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d+)?\s*[kK])")


def _money(tok):
    tok = tok.strip().replace(",", "")
    if tok.lower().endswith("k"):
        return int(round(float(tok[:-1]) * 1000))
    return int(tok)


def parse_salary_text(text):
    """Pull an annual USD range from free text. Returns (min, max) or (None, None).
    Skips matches that look hourly/monthly (values under $20k)."""
    if not text:
        return (None, None)
    for m in _SALARY_RANGE_RE.finditer(text):
        try:
            lo, hi = _money(m.group(1)), _money(m.group(2))
        except ValueError:
            continue
        if 20_000 <= lo <= hi <= 1_500_000:
            return (lo, hi)
    return (None, None)


# ---------------------------------------------------------------------------
# per-platform feed fetchers -> (roles, meta)
# role = {title, url, location, job_id, posting_date, comp_min, comp_max,
#         remote_hint, country, slug_text}
# meta = {result, http, error, total, complete}
# ---------------------------------------------------------------------------
def _date_from_iso(s):
    if not s:
        return None
    try:
        return str(s)[:10]
    except Exception:
        return None


def _date_from_ms(ms):
    try:
        return datetime.date.fromtimestamp(int(ms) / 1000).isoformat()
    except Exception:
        return None


def fetch_greenhouse(slug, timeout):
    url = f"https://boards-api.greenhouse.io/v1/boards/{urllib.parse.quote(slug, safe='')}/jobs?content=true"
    result, code, payload, err = _request(url, timeout)
    if result != "ok":
        return [], {"result": result, "http": code, "error": err, "total": None, "complete": False}
    roles = []
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        content = html.unescape(j.get("content") or "")
        lo, hi = (None, None)
        for pr in (j.get("pay_input_ranges") or []):
            try:
                lo = int(pr["min_cents"]) // 100
                hi = int(pr["max_cents"]) // 100
                break
            except (KeyError, TypeError, ValueError):
                lo, hi = (None, None)
        if lo is None:
            lo, hi = parse_salary_text(content)
        roles.append({
            "title": j.get("title") or "?",
            "url": j.get("absolute_url") or "",
            "location": ((j.get("location") or {}).get("name")) or "",
            "job_id": str(j.get("id") or ""),
            "posting_date": _date_from_iso(j.get("first_published") or j.get("updated_at")),
            "comp_min": lo, "comp_max": hi,
            "remote_hint": False, "country": None,
            "slug_text": j.get("absolute_url") or "",
        })
    return roles, {"result": "ok", "http": 200, "error": None,
                   "total": len(roles), "complete": True}


def fetch_lever(slug, timeout):
    q = urllib.parse.quote(slug, safe="")
    for host in ("https://api.lever.co", "https://api.eu.lever.co"):
        url = f"{host}/v0/postings/{q}?mode=json"
        result, code, payload, err = _request(url, timeout)
        if result == "miss":
            continue  # US 404 -> try EU instance
        if result != "ok":
            return [], {"result": result, "http": code, "error": err, "total": None, "complete": False}
        roles = []
        jobs = payload if isinstance(payload, list) else []
        for j in jobs:
            if not isinstance(j, dict):
                continue
            cats = j.get("categories") or {}
            sal = j.get("salaryRange") or {}
            lo = hi = None
            interval = (sal.get("interval") or "").lower()
            if sal.get("min") and sal.get("max") and ("year" in interval or not interval):
                try:
                    lo, hi = int(sal["min"]), int(sal["max"])
                    if lo < 20_000:  # hourly/monthly mislabeled - don't trust it
                        lo = hi = None
                except (TypeError, ValueError):
                    lo = hi = None
            if lo is None:
                lo, hi = parse_salary_text(j.get("descriptionPlain") or "")
            roles.append({
                "title": j.get("text") or "?",
                "url": j.get("hostedUrl") or j.get("applyUrl") or "",
                "location": cats.get("location") or "",
                "job_id": str(j.get("id") or ""),
                "posting_date": _date_from_ms(j.get("createdAt")),
                "comp_min": lo, "comp_max": hi,
                "remote_hint": (j.get("workplaceType") or "").lower() == "remote",
                "country": j.get("country"),
                "slug_text": j.get("hostedUrl") or "",
            })
        return roles, {"result": "ok", "http": 200, "error": None,
                       "total": len(roles), "complete": True}
    return [], {"result": "miss", "http": 404, "error": None, "total": None, "complete": False}


def fetch_ashby(slug, timeout):
    url = (f"https://api.ashbyhq.com/posting-api/job-board/"
           f"{urllib.parse.quote(slug, safe='')}?includeCompensation=true")
    result, code, payload, err = _request(url, timeout)
    if result != "ok":
        return [], {"result": result, "http": code, "error": err, "total": None, "complete": False}
    roles = []
    for j in (payload.get("jobs", []) if isinstance(payload, dict) else []):
        if not isinstance(j, dict):
            continue
        locs = [j.get("location") or ""]
        for sec in (j.get("secondaryLocations") or []):
            if isinstance(sec, dict) and sec.get("location"):
                locs.append(sec["location"])
        comp = j.get("compensation") or {}
        lo, hi = parse_salary_text(comp.get("compensationTierSummary") or "")
        roles.append({
            "title": j.get("title") or "?",
            "url": j.get("jobUrl") or j.get("applyUrl") or "",
            "location": "; ".join(x for x in locs if x),
            "job_id": str(j.get("id") or ""),
            "posting_date": _date_from_iso(j.get("publishedAt") or j.get("publishedDate")),
            "comp_min": lo, "comp_max": hi,
            "remote_hint": bool(j.get("isRemote")),
            "country": None,
            "slug_text": j.get("jobUrl") or "",
        })
    return roles, {"result": "ok", "http": 200, "error": None,
                   "total": len(roles), "complete": True}


def fetch_workable(slug, timeout):
    url = f"https://apply.workable.com/api/v1/widget/accounts/{urllib.parse.quote(slug, safe='')}"
    result, code, payload, err = _request(url, timeout)
    if result != "ok":
        return [], {"result": result, "http": code, "error": err, "total": None, "complete": False}
    roles = []
    for j in (payload.get("jobs", []) if isinstance(payload, dict) else []):
        if not isinstance(j, dict):
            continue
        loc = j.get("location") or ", ".join(
            x for x in (j.get("city"), j.get("state"), j.get("country")) if x)
        # Workable shortcodes come back UPPERCASE; stored dedup keys are lowercased.
        shortcode = str(j.get("shortcode") or "").lower()
        roles.append({
            "title": j.get("title") or "?",
            "url": j.get("shortlink") or j.get("url") or j.get("application_url")
                   or (f"https://apply.workable.com/j/{shortcode.upper()}" if shortcode else ""),
            "location": loc or "",
            "job_id": shortcode,
            "posting_date": _date_from_iso(j.get("published_on") or j.get("created_at")),
            "comp_min": None, "comp_max": None,
            "remote_hint": bool(j.get("telecommuting") or j.get("remote")),
            "country": j.get("country"),
            "slug_text": j.get("shortlink") or "",
        })
    return roles, {"result": "ok", "http": 200, "error": None,
                   "total": len(roles), "complete": True}


def fetch_rippling(slug, timeout):
    url = f"https://api.rippling.com/platform/api/ats/v1/board/{urllib.parse.quote(slug, safe='')}/jobs"
    result, code, payload, err = _request(url, timeout)
    if result != "ok":
        return [], {"result": result, "http": code, "error": err, "total": None, "complete": False}
    jobs = payload if isinstance(payload, list) else (
        payload.get("jobs", []) if isinstance(payload, dict) else [])
    roles = []
    for j in jobs:
        if not isinstance(j, dict):
            continue
        w = j.get("workLocation") or j.get("location") or {}
        loc = (w.get("label") or w.get("name")) if isinstance(w, dict) else (w or "")
        roles.append({
            "title": j.get("name") or j.get("title") or "?",
            "url": j.get("url") or j.get("jobUrl") or "",
            "location": loc or "",
            "job_id": str(j.get("id") or j.get("uuid") or ""),
            "posting_date": _date_from_iso(j.get("createdAt") or j.get("publishedAt")),
            "comp_min": None, "comp_max": None,
            "remote_hint": REMOTE_RE.search(str(loc or "")) is not None,
            "country": None,
            "slug_text": j.get("url") or "",
        })
    return roles, {"result": "ok", "http": 200, "error": None,
                   "total": len(roles), "complete": True}


def fetch_smartrecruiters(slug, timeout):
    q = urllib.parse.quote(slug, safe="")
    url = f"https://api.smartrecruiters.com/v1/companies/{q}/postings?limit=100"
    result, code, payload, err = _request(url, timeout)
    if result != "ok":
        return [], {"result": result, "http": code, "error": err, "total": None, "complete": False}
    items = payload.get("content", []) if isinstance(payload, dict) else []
    total = payload.get("totalFound")
    roles = []
    for j in items:
        if not isinstance(j, dict):
            continue
        l = j.get("location") or {}
        loc = ", ".join(x for x in (l.get("city"), l.get("region"), l.get("country")) if x)
        jid = str(j.get("id") or "")
        roles.append({
            "title": j.get("name") or "?",
            "url": f"https://jobs.smartrecruiters.com/{slug}/{jid}",
            "location": loc,
            "job_id": jid,
            "posting_date": _date_from_iso(j.get("releasedDate")),
            "comp_min": None, "comp_max": None,
            "remote_hint": bool(l.get("remote")),
            "country": (l.get("country") or "").upper() or None,
            "slug_text": j.get("name") or "",
        })
    complete = not (isinstance(total, int) and total > len(roles))
    return roles, {"result": "ok", "http": 200, "error": None,
                   "total": total if isinstance(total, int) else len(roles),
                   "complete": complete}


def fetch_bamboohr(slug, timeout):
    q = urllib.parse.quote(slug, safe="")
    url = f"https://{q}.bamboohr.com/careers/list"
    result, code, payload, err = _request(url, timeout)
    if result != "ok":
        return [], {"result": result, "http": code, "error": err, "total": None, "complete": False}
    roles = []
    for j in (payload.get("result", []) if isinstance(payload, dict) else []):
        if not isinstance(j, dict):
            continue
        l = j.get("location") or {}
        loc = (", ".join(x for x in (l.get("city"), l.get("state")) if x)
               if isinstance(l, dict) else str(l or ""))
        jid = str(j.get("id") or "")
        roles.append({
            "title": j.get("jobOpeningName") or j.get("title") or "?",
            "url": f"https://{slug}.bamboohr.com/careers/{jid}",
            "location": loc,
            "job_id": jid,
            "posting_date": None,  # the public list carries no date
            "comp_min": None, "comp_max": None,
            "remote_hint": bool(j.get("isRemote")),
            "country": None,
            "slug_text": j.get("jobOpeningName") or "",
        })
    return roles, {"result": "ok", "http": 200, "error": None,
                   "total": len(roles), "complete": True}


def fetch_recruitee(slug, timeout):
    q = urllib.parse.quote(slug, safe="")
    url = f"https://{q}.recruitee.com/api/offers/"
    result, code, payload, err = _request(url, timeout)
    if result != "ok":
        return [], {"result": result, "http": code, "error": err, "total": None, "complete": False}
    roles = []
    for j in (payload.get("offers", []) if isinstance(payload, dict) else []):
        if not isinstance(j, dict):
            continue
        loc = j.get("location") or ", ".join(
            x for x in (j.get("city"), j.get("country")) if x)
        roles.append({
            "title": j.get("title") or "?",
            "url": j.get("careers_url") or j.get("url") or "",
            "location": loc or "",
            "job_id": str(j.get("id") or ""),
            "posting_date": _date_from_iso(j.get("created_at")),
            "comp_min": None, "comp_max": None,
            "remote_hint": bool(j.get("remote")),
            "country": (j.get("country_code") or "").upper() or None,
            "slug_text": j.get("careers_url") or "",
        })
    return roles, {"result": "ok", "http": 200, "error": None,
                   "total": len(roles), "complete": True}


# --- Workday ----------------------------------------------------------------
WD_HOST_RE = re.compile(r"https?://([^.]+)\.wd(\d+)\.myworkdayjobs\.com", re.I)
WD_REQID_RE = re.compile(r"_([A-Za-z0-9][A-Za-z0-9-]*?)(?:-(\d+))?$")
WD_POSTED_RE = re.compile(r"(?i)posted\s+(today|yesterday|(\d+)\+?\s+days?\s+ago)")


def workday_target(company):
    """Derive (tenant, site, host) from a company row (ats_slug='tenant/site',
    careers_url carries the wdN host). Returns None with a reason when unaddressable."""
    slug = company.get("ats_slug") or ""
    m = WD_HOST_RE.search(company.get("careers_url") or "")
    if "/" not in slug or not m:
        return None, "workday tenant/site/wdN not derivable (need ats_slug='tenant/site' and a myworkdayjobs careers_url)"
    tenant, site = slug.split("/", 1)
    host = f"https://{m.group(1)}.wd{m.group(2)}.myworkdayjobs.com"
    return (tenant, site, host), None


def wd_reqid(external_path, strip_suffix):
    """Reqid from an externalPath. Strips the trailing -N instance suffix unless the
    tenant's scheme keeps it (UCAR REQ-YYYY-WK-N)."""
    m = WD_REQID_RE.search(external_path or "")
    if not m:
        return None
    rid = m.group(1)
    if not strip_suffix and m.group(2):
        rid = f"{rid}-{m.group(2)}"
    return rid.lower()


def wd_posting_date(posted_on):
    m = WD_POSTED_RE.search(posted_on or "")
    if not m:
        return None
    if m.group(1).lower() == "today":
        return today()
    if m.group(1).lower() == "yesterday":
        return (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    if "+" in m.group(1):
        return None  # "30+ days ago" - too vague to anchor
    try:
        return (datetime.date.today() - datetime.timedelta(days=int(m.group(2)))).isoformat()
    except (TypeError, ValueError):
        return None


def fetch_workday(tenant, site, host, timeout, keywords, max_pages, strip_suffix):
    """Paginated CXS list fetch. For big tenants (total > max_pages*20 on the empty
    search) falls back to per-keyword searches - feed marked incomplete either way
    unless everything was pulled (missing roles get an individual detail GET later)."""
    list_url = f"{host}/wday/cxs/{tenant}/{urllib.parse.quote(site, safe='')}/jobs"
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}

    def page(search_text, offset):
        body = json.dumps({"limit": 20, "offset": offset, "searchText": search_text,
                           "appliedFacets": {}}).encode("utf-8")
        return _request(list_url, timeout, data=body, headers=hdrs)

    seen = {}
    total = None
    complete = True

    def collect(search_text):
        nonlocal total, complete
        offset = 0
        for _ in range(max_pages):
            result, code, payload, err = page(search_text, offset)
            if result != "ok":
                return (result, code, err)
            posts = payload.get("jobPostings") or []
            if search_text == "" and total is None:
                total = payload.get("total")
            for p in posts:
                ep = p.get("externalPath") or ""
                if ep and ep not in seen:
                    seen[ep] = p
            if len(posts) < 20:
                return ("ok", 200, None)
            offset += 20
        complete = False  # ran out of pages before the feed ran out of jobs
        return ("ok", 200, None)

    result, code, err = collect("")
    if result != "ok":
        return [], {"result": result, "http": code, "error": err, "total": None, "complete": False}
    if total and total > max_pages * 20:
        # Big tenant: the empty-search pull is capped. Sweep per keyword instead.
        complete = False
        for kw in keywords[:6]:
            collect(kw)

    roles = []
    for ep, p in seen.items():
        rid = wd_reqid(ep, strip_suffix)
        # Human-facing URL: externalPath OMITS the careersite segment - insert it.
        roles.append({
            "title": p.get("title") or "?",
            "url": f"{host}/{site}{ep}",
            "location": p.get("locationsText") or "",
            "job_id": rid or "",
            "posting_date": wd_posting_date(p.get("postedOn")),
            "comp_min": None, "comp_max": None,
            "remote_hint": REMOTE_RE.search(p.get("locationsText") or "") is not None,
            "country": None,
            "slug_text": ep,  # CXS title can drop seniority that IS in the path slug
        })
    return roles, {"result": "ok", "http": 200, "error": None,
                   "total": total if total is not None else len(roles),
                   "complete": complete}


def wd_detail_check(stored_url, tenant, site, host, timeout):
    """Confirm one stored Workday role via the CXS job-detail GET: 200=live, 404=gone,
    anything else=inconclusive. Derives the externalPath from the stored human URL."""
    prefix = f"{host}/{site}"
    if not (stored_url or "").startswith(prefix):
        return ("unknown", None, "stored url does not match tenant host/site")
    external_path = stored_url[len(prefix):]
    url = f"{host}/wday/cxs/{tenant}/{urllib.parse.quote(site, safe='')}{external_path}"
    result, code, _, err = _request(url, timeout)
    if result == "ok":
        return ("live", 200, None)
    if result == "miss":
        return ("gone", 404, None)
    return ("unknown", code, err)


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workable": fetch_workable,
    "rippling": fetch_rippling,
    "smartrecruiters": fetch_smartrecruiters,
    "bamboohr": fetch_bamboohr,
    "recruitee": fetch_recruitee,
    # workday handled separately (needs tenant/site/host + pagination args)
}


# ---------------------------------------------------------------------------
# candidate-driven filters
# ---------------------------------------------------------------------------
def constraint_states(constraint):
    """Extract accepted state codes from the stored location constraint, e.g.
    'Arvada, CO - Colorado-based or fully remote only' -> [('CO', 'Colorado')]."""
    text = constraint or ""
    found = {}
    for code, name in US_STATES.items():
        if re.search(rf"(?i)\b{re.escape(name)}\b", text):
            found[code] = name
    for m in re.finditer(r"\b([A-Z]{2})\b", text):
        if m.group(1) in US_STATES:
            found[m.group(1)] = US_STATES[m.group(1)]
    return sorted(found.items())


def location_verdict(role, states, allow_remote):
    """'state' | 'remote' | 'ambiguous' | None (no match)."""
    loc = role.get("location") or ""
    if AMBIGUOUS_LOC_RE.match(loc):
        return "ambiguous"
    for code, name in states:
        if re.search(rf"(?i)\b{re.escape(name)}\b", loc) or re.search(rf"\b{code}\b", loc):
            return "state"
    if allow_remote and (role.get("remote_hint") or REMOTE_RE.search(loc)):
        us = US_TOKEN_RE.search(loc) or (role.get("country") or "").upper() in ("US", "USA")
        if us:
            return "remote"
    return None


def build_keyword_matcher(categories):
    """Per-category keyword matcher. A title matches a keyword when ALL its tokens
    appear (any order: 'software engineer' hits 'Software Development Engineer'), or
    when a distinctive token appears alone. Distinctive = a single-word keyword
    ('qiskit', 'backend', 'SIEM'), or a token recurring across 2+ of the category's
    keywords ('quantum' in 'quantum software, quantum computing, ...'). A token seen
    in only ONE multi-word keyword is NOT distinctive on its own - that is how
    'learning' (from 'machine learning engineer') would otherwise match HR
    'Learning and Development' roles. Returns title -> category label (best rank)."""
    cats = []
    for rank, label, keywords in categories:
        kw_tokensets, distinctive, token_count = [], set(), {}
        for kw in (keywords or "").split(","):
            toks = [t for t in re.split(r"[^a-z0-9+#]+", kw.strip().lower()) if t]
            if not toks:
                continue
            kw_tokensets.append(toks)
            if len(toks) == 1 and toks[0] not in GENERIC_TOKENS:
                distinctive.add(toks[0])
            for t in set(toks):
                token_count[t] = token_count.get(t, 0) + 1
        for t, n in token_count.items():
            if n >= 2 and len(t) >= 6 and t not in GENERIC_TOKENS:
                distinctive.add(t)
        cats.append((rank, label, kw_tokensets, distinctive))
    cats.sort(key=lambda c: c[0])

    def match(title):
        toks = set(re.split(r"[^a-z0-9+#]+", (title or "").lower()))
        for _, label, kw_tokensets, distinctive in cats:
            for ts in kw_tokensets:
                if all(t in toks for t in ts):
                    return label
            if toks & distinctive:
                return label
        return None
    return match


def remote_type_of(role, verdict):
    loc = role.get("location") or ""
    if verdict == "remote":
        return "remote"
    if HYBRID_RE.search(loc):
        return "hybrid"
    if REMOTE_RE.search(loc) or role.get("remote_hint"):
        return "remote"
    return "unknown"


# ---------------------------------------------------------------------------
# DB access (read-only)
# ---------------------------------------------------------------------------
def connect_ro():
    if not os.path.exists(DB_PATH):
        sys.exit(f"Database not found at {DB_PATH}.")
    uri = f"file:{urllib.request.pathname2url(os.path.abspath(DB_PATH)).lstrip('/')}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.OperationalError:
        conn = sqlite3.connect(DB_PATH)  # fallback; this script still never writes
    conn.row_factory = sqlite3.Row
    return conn


def load_candidate(conn, slug):
    row = conn.execute("SELECT * FROM candidates WHERE slug = ?", (slug,)).fetchone()
    if not row:
        sys.exit(f"No candidate '{slug}'. See: python jobsdb.py candidate list")
    cand = dict(row)
    cats = conn.execute(
        "SELECT rank, label, keywords FROM candidate_categories "
        "WHERE candidate_id = ? ORDER BY rank", (row["id"],)).fetchall()
    cand["categories"] = [(c["rank"], c["label"], c["keywords"]) for c in cats]
    return cand


def load_companies(conn, only_names=None):
    rows = conn.execute(
        "SELECT * FROM companies WHERE verification_status = 'feed_verified' "
        "ORDER BY name").fetchall()
    companies = [dict(r) for r in rows]
    if only_names:
        wanted = {n.lower() for n in only_names}
        companies = [c for c in companies if c["name"].lower() in wanted
                     or any(w in c["name"].lower() for w in wanted)]
    return companies


def load_jobs(conn, candidate_id):
    """(all_keys, live) — all_keys spans EVERY status: a job the candidate ignored,
    applied to, or that expired must not be re-proposed as net-new. live (new/active
    only) drives presence-confirmation and expiry checks."""
    rows = conn.execute(
        "SELECT j.id, j.dedup_key, j.title, j.status, j.tier, j.url, j.comp_min, "
        "COALESCE(co.name,'') AS company "
        "FROM jobs j LEFT JOIN companies co ON co.id = j.company_id "
        "WHERE j.candidate_id = ?", (candidate_id,)).fetchall()
    all_keys = {r["dedup_key"] for r in rows}
    live = {r["dedup_key"]: dict(r) for r in rows if r["status"] in ("new", "active")}
    return all_keys, live


# ---------------------------------------------------------------------------
# sweep
# ---------------------------------------------------------------------------
def sweep(args):
    conn = connect_ro()
    cand = load_candidate(conn, args.candidate)
    companies = load_companies(conn, args.company)
    all_keys, stored = load_jobs(conn, cand["id"])
    conn.close()

    level_re_src = (cand.get("seniority_filter") or "").strip() or DEFAULT_LEVEL_RE
    try:
        level_re = re.compile(level_re_src)
    except re.error as e:
        sys.exit(f"Invalid seniority_filter regex for candidate: {e}")
    # Word-boundary matching so 'crypto' does NOT hit 'cryptography' (a real concern
    # for a quantum candidate excluding crypto/web3 companies).
    exclusions = [re.compile(rf"(?i)\b{re.escape(x.strip())}\b")
                  for x in (cand.get("exclusions") or "").split(",") if x.strip()]
    states = constraint_states(cand.get("location_constraint"))
    allow_remote = "remote" in (cand.get("location_constraint") or "").lower()
    if not states and not allow_remote:
        sys.exit("Candidate has no parseable location constraint (no state, no remote).")
    kw_match = build_keyword_matcher(cand["categories"])
    all_keywords = [kw.strip() for _, _, kws in cand["categories"]
                    for kw in (kws or "").split(",") if kw.strip()]
    keep_suffix_tenants = {t.lower() for t in (args.keep_suffix_tenant or ["ucar"])}

    new_roles, feeds, skipped = [], [], []
    confirmed, missing, ambiguous, comp_updates = [], [], [], []
    counts = {"fetched": 0, "over_level": 0, "wrong_location": 0, "no_keyword": 0,
              "excluded": 0, "ambiguous_location": 0, "already_tracked": 0}
    seen_keys_global = set()

    for co in companies:
        platform = (co.get("ats_platform") or "").lower()
        slug = co.get("ats_slug") or ""
        if platform == "workday":
            target, why = workday_target(co)
            if not target:
                skipped.append({"company": co["name"], "reason": why})
                continue
            tenant, site, host = target
            strip = tenant.lower() not in keep_suffix_tenants
            roles, meta = fetch_workday(tenant, site, host, args.timeout,
                                        all_keywords, args.workday_pages, strip)
            key_prefix = f"workday:{tenant.lower()}:"
            make_key = lambda r: f"workday:{tenant.lower()}:{r['job_id']}"
        elif platform in FETCHERS and slug:
            roles, meta = FETCHERS[platform](slug, args.timeout)
            key_prefix = f"{platform}:{slug.lower()}:"
            make_key = lambda r, p=platform, s=slug: f"{p}:{s.lower()}:{r['job_id'].lower()}"
        else:
            skipped.append({"company": co["name"],
                            "reason": f"unsupported platform '{platform or '-'}' or missing slug"})
            continue

        feed = {"company": co["name"], "platform": platform, "slug": slug,
                "result": meta["result"], "http": meta["http"], "error": meta["error"],
                "total": meta["total"], "complete": meta["complete"], "kept_new": 0}

        if meta["result"] != "ok":
            feeds.append(feed)
            continue

        counts["fetched"] += len(roles)
        feed_keys = set()
        for r in roles:
            if not r["job_id"]:
                continue
            key = make_key(r)
            feed_keys.add(key)
            if key in all_keys or key in seen_keys_global:
                if key in all_keys:
                    counts["already_tracked"] += 1
                    # Comp backfill (live rows only): the feed publishes a range the DB lacks.
                    if key in stored and r["comp_min"] and not stored[key].get("comp_min"):
                        comp_updates.append({"id": stored[key]["id"],
                                             "company": stored[key]["company"],
                                             "title": stored[key]["title"],
                                             "comp_min": r["comp_min"],
                                             "comp_max": r["comp_max"]})
                continue
            # --- filters (order: level -> exclusion -> keyword -> location, so the
            # ambiguous-location list only carries roles actually worth checking) ---
            level_text = f"{r['title']} {r['slug_text'].replace('-', ' ').replace('_', ' ')}"
            if not args.include_over_level and level_re.search(level_text):
                counts["over_level"] += 1
                continue
            blob = f"{co['name']} {r['title']}"
            if any(x.search(blob) for x in exclusions):
                counts["excluded"] += 1
                continue
            category = kw_match(r["title"])
            if category is None and not args.no_keyword_filter:
                counts["no_keyword"] += 1
                continue
            verdict = location_verdict(r, states, allow_remote)
            if verdict == "ambiguous":
                counts["ambiguous_location"] += 1
                ambiguous.append({"company": co["name"], "title": r["title"],
                                  "url": r["url"], "location": r["location"]})
                continue
            if verdict is None:
                counts["wrong_location"] += 1
                continue
            seen_keys_global.add(key)
            feed["kept_new"] += 1
            new_roles.append({
                "company": co["name"],
                "careers_url": co.get("careers_url"),
                "ats_platform": "workday" if platform == "workday" else platform,
                "ats_slug": slug,
                "dedup_key": key,
                "title": r["title"],
                "url": r["url"],
                "ats_job_id": r["job_id"],
                "location": r["location"],
                "remote_type": remote_type_of(r, verdict),
                "location_match": True,
                "comp_min": r["comp_min"],
                "comp_max": r["comp_max"],
                "posting_date": r["posting_date"],
                "verification_tag": "verified",
                "tier": None,
                "category_label": category,
                "fit_summary": "",
                "screening_risks": "",
            })

        # --- presence diff for stored live roles on this feed ---
        for key, job in stored.items():
            if not key.startswith(key_prefix):
                continue
            present = key in feed_keys
            if not present and platform == "workday":
                # legacy suffixed keys (pre-strip-rule rows): match modulo -N
                base = re.sub(r"-\d+$", "", key)
                present = base in feed_keys or any(
                    re.sub(r"-\d+$", "", fk) == base for fk in feed_keys)
            if present:
                confirmed.append(job["id"])
            elif platform == "workday":
                # NEVER auto-expire a Workday role on list absence - detail-check it.
                verdict2, http2, err2 = wd_detail_check(job["url"], tenant, site, host,
                                                        args.timeout)
                missing.append({"id": job["id"], "company": job["company"],
                                "title": job["title"],
                                "verdict": {"live": "confirmed-live (detail GET 200)",
                                            "gone": "expire (detail GET 404)",
                                            "unknown": f"inconclusive ({err2 or http2})"}[verdict2]})
                if verdict2 == "live":
                    confirmed.append(job["id"])
            elif meta["complete"]:
                missing.append({"id": job["id"], "company": job["company"],
                                "title": job["title"],
                                "verdict": "expire (absent from fully-pulled feed)"})
            else:
                missing.append({"id": job["id"], "company": job["company"],
                                "title": job["title"],
                                "verdict": "inconclusive (feed incomplete)"})
        feeds.append(feed)
        if not args.quiet:
            status = (f"{feed['total']} in feed, +{feed['kept_new']} new"
                      if meta["result"] == "ok" else f"{meta['result']}: {meta['error']}")
            print(f"  [{platform:<10}] {co['name']:<38} {status}")

    return {
        "candidate": cand["slug"], "run_date": today(),
        "companies_swept": len(feeds), "companies_skipped": skipped,
        "feeds": feeds, "counts": counts,
        "new_roles": new_roles,
        "confirmed_live_ids": sorted(set(confirmed)),
        "missing": missing, "ambiguous": ambiguous,
        "comp_updates": comp_updates,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Sweep all feed-verified companies' ATS feeds: diff against the "
                    "stored pipeline, draft net-new roles, confirm/flag stored ones.")
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--out", help="Write the net-new draft batch JSON here "
                                  "(e.g. job_scans/YYYY-MM-DD_sweep-draft.json)")
    ap.add_argument("--report", help="Write the full machine-readable report JSON here")
    ap.add_argument("--company", action="append",
                    help="Only sweep companies whose name contains this (repeatable)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--workday-pages", type=int, default=15,
                    help="Max CXS pages (of 20) per Workday tenant/search (default 15)")
    ap.add_argument("--keep-suffix-tenant", action="append",
                    help="Workday tenant whose reqid keeps its trailing -N "
                         "(default: ucar). Repeatable.")
    ap.add_argument("--no-keyword-filter", action="store_true",
                    help="Keep roles even when no category keyword matches")
    ap.add_argument("--include-over-level", action="store_true",
                    help="Keep senior/staff/intern roles the level filter would drop")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    print(f"Sweeping feed-verified companies for '{args.candidate}'...")
    res = sweep(args)
    c = res["counts"]

    print(f"\n=== Sweep summary ({res['run_date']}) ===")
    print(f"  companies swept: {res['companies_swept']}"
          + (f"  (skipped {len(res['companies_skipped'])}: "
             + "; ".join(s['company'] for s in res['companies_skipped']) + ")"
             if res["companies_skipped"] else ""))
    errored = [f for f in res["feeds"] if f["result"] != "ok"]
    if errored:
        print(f"  FEED ERRORS (blind spots, not empty results):")
        for f in errored:
            print(f"    !! {f['company']} [{f['platform']}:{f['slug']}] "
                  f"{f['error'] or f['http']}")
    print(f"  roles fetched: {c['fetched']}  |  already tracked: {c['already_tracked']}")
    print(f"  filtered out: {c['over_level']} over-level/non-FTE, "
          f"{c['wrong_location']} wrong-location, {c['no_keyword']} no-keyword-match, "
          f"{c['excluded']} excluded-industry, {c['ambiguous_location']} ambiguous-location")
    print(f"  NET-NEW candidate roles: {len(res['new_roles'])}")
    for r in res["new_roles"]:
        comp = (f"  ${r['comp_min']//1000}k-${r['comp_max']//1000}k"
                if r["comp_min"] and r["comp_max"] else "")
        print(f"    + {r['company']}: {r['title']}  ({r['location']}){comp}")
        print(f"      {r['url']}")

    if res["confirmed_live_ids"]:
        ids = " ".join(str(i) for i in res["confirmed_live_ids"])
        print(f"\n  {len(res['confirmed_live_ids'])} stored role(s) confirmed live. Record:")
        print(f"    python jobsdb.py mark {ids} --verified")
    expire = [m for m in res["missing"] if m["verdict"].startswith("expire")]
    inconclusive = [m for m in res["missing"] if m["verdict"].startswith("inconclusive")]
    if expire:
        print(f"\n  {len(expire)} stored role(s) GONE from their feed (expiry candidates):")
        for m in expire:
            print(f"    id={m['id']:<4} {m['company']}: {m['title']}  [{m['verdict']}]")
        print(f"    python jobsdb.py mark {' '.join(str(m['id']) for m in expire)} --status expired")
    if inconclusive:
        print(f"\n  {len(inconclusive)} role(s) INCONCLUSIVE (incomplete feed / error) - "
              "re-verify manually:")
        for m in inconclusive:
            print(f"    id={m['id']:<4} {m['company']}: {m['title']}")
    if res["comp_updates"]:
        print(f"\n  {len(res['comp_updates'])} stored role(s) now show a posted range "
              "the DB lacks (comp backfill):")
        for u in res["comp_updates"]:
            hi = f" --comp-max {u['comp_max']}" if u["comp_max"] else ""
            print(f"    python jobsdb.py mark {u['id']} --comp-min {u['comp_min']}{hi}"
                  f"   # {u['company']}: {u['title']}")
    if res["ambiguous"]:
        print(f"\n  {len(res['ambiguous'])} new role(s) with ambiguous multi-location "
              "(check per-role location before considering):")
        for a in res["ambiguous"]:
            print(f"    {a['company']}: {a['title']}  ({a['location']})  {a['url']}")

    if args.out and res["new_roles"]:
        batch = {"candidate": res["candidate"], "run_date": res["run_date"],
                 "notes": "sweep.py draft - tiers/fit pending agent review",
                 "jobs": res["new_roles"]}
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(batch, f, indent=2)
        print(f"\nDraft batch written: {args.out}")
        print("  Review it (assign tier / fit_summary / screening_risks per role), then:")
        print(f"    python jobsdb.py upsert-batch {args.out}")
    elif args.out:
        print("\nNo net-new roles - no draft batch written.")

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        print(f"Full report written: {args.report}")


if __name__ == "__main__":
    main()
