---
name: job-search
description: >
  Comprehensive job opportunity discovery for a candidate based on their resume or profile.
  Use this skill whenever a user shares a resume, asks to find jobs, says "find me roles",
  "search for opportunities", "help my friend find a job", or provides any candidate profile
  for job searching. This skill runs a thorough multi-source search starting with company
  careers pages and ATS subdomains, then falling back to job boards, LinkedIn, Google Jobs,
  Indeed, and domain-specific boards. Every role is verified live, date-anchored, AND
  location-matched against the candidate's stored location constraint before being reported.
  Always use this skill rather than a simple web search when job discovery is the goal —
  it will find significantly more and better-matched opportunities.
---

# Job Search Skill

## Overview

This skill finds job opportunities a candidate would struggle to discover on their own.
Three key insights drive the approach:

1. **The company's own careers page is the only authoritative source.** Aggregators,
   LinkedIn, and ATS-indexing sites all lag and frequently fail to remove expired
   listings. Roles must be verified against the company's own surface before being
   recommended.
2. **Search starts with companies, not job boards.** Searching boards directly misses
   40–60% of relevant roles.
3. **A live posting is not the same as a matching posting.** A role can be verified live
   on the company ATS but still be useless to the candidate if it's in the wrong city,
   the wrong country, or in-office-only when they need remote. Location verification is a
   mandatory gate, not an afterthought.

---

## Phase 1: Profile Extraction

Before searching, extract a structured candidate brief from the resume or profile provided.

### Step 1a: Read from the database first

Check the **database** for an existing candidate BEFORE asking the user (see `database.md`):

```
python jobsdb.py candidate list
python jobsdb.py candidate show --slug <slug>
```

The candidate record and their ranked categories hold:

- Candidate name and city/state of residence
- Location constraint (e.g. "Colorado-based or fully remote only, no relocation")
- Citizenship and clearance status
- Comp floor / target
- **Ranked category priority** (`candidate_categories`) — the industries/role types this
  candidate wants, in priority order. This drives which searches run and how thoroughly.
- Companies on cooldown or to avoid (notes)

If the candidate exists, state their brief back for confirmation. Do not re-ask known
fields. If this is a new resume with no DB match, extract the profile below and register
the candidate (and their categories) per `Project_Instructions.md` Step 3. Claude Code
memory may supply supplementary context, but the DB is authoritative.

### Step 1b: Extract from the resume/profile

For any fields not in memory, extract from the materials provided:

- **Technical domain(s)**: Primary field + adjacent areas
- **Role types**: What kinds of roles fit (engineer, TPM, architect, hybrid)
- **Seniority level**: Years of experience, title progression, team size led
- **Location**: City, metro, remote preference — REQUIRED, do not proceed without it
- **Comp target**: If stated; otherwise note "not specified"
- **Key differentiators**: 2–3 things that make this candidate unusual or strong
- **Screening risks**: Known gaps (tools, domain, level) that will filter them out
- **Constraints**: Companies/industries to avoid, relocation preference
- **Warm signals**: Any companies, recruiters, or contacts already identified

Resumes rarely state work authorization, security clearance, location/remote preference,
comp floor, or relocation — yet these drive the Phase 4c location gate and Phase 5
screening-risk flags. For a **new** candidate, run the **`onboarding-questionnaire.md`**
to capture them. Only ask what the resume/memory don't already supply.

### Step 1c: Confirm and save to the database

Output the brief and confirm framing with the user before proceeding. Register or update
the candidate and their ranked categories in the database (`jobsdb.py candidate add` /
`category set` — see `Project_Instructions.md` Step 3) so the brief persists across
sessions and is reusable by other candidates who run this project with their own resume.

**Location is a required field.** If the user has not provided a location constraint
and none is in memory, ask explicitly: "Where do you want to work? Specific cities, a
metro area, remote only, or remote with occasional travel?" Do not begin searching
without a clear location answer.

---

## Phase 2: Company List Construction

**Do not start with job board searches.** Start with companies.

### Step 2a: Domain Mapping
Work through the candidate's **ranked categories** (from `candidate_categories`) in
priority order — build the company list for the rank-1 category most thoroughly, then
rank-2, then rank-3. Tag each company and resulting role with the `category_label` it came
from so the pipeline can be queried by category later (e.g. `query --category quantum`).

Based on the candidate's qualifications, identify 3–5 company categories that hire this
profile. This is **domain-driven** — derive it from the resume + ranked categories, not a
fixed list. Examples across fields:
- Optical/EO engineer → space imaging startups, defense-tech, laser companies, national labs
- ML engineer → AI infrastructure, autonomous systems, applied AI companies
- Mechanical engineer → aerospace, robotics, hardware startups, defense
- IT / systems administrator → MSPs & managed-IT providers, healthcare & hospital systems,
  universities & school districts, financial-services & insurance IT, state/local government,
  datacenter/colocation & cloud operators, and the internal IT of any large local employer
- Registered nurse → hospital systems, clinics, telehealth, travel-nursing agencies

See `domain-boards.md` for board sources per domain, and `examples/it-sysadmin-profile.md`
for a worked non-engineering example.

### Step 2b: Build Target Company List
Search for companies in each category matching:
- Location constraint (or remote-friendly)
- Funding stage / size preference (if stated)
- Domain alignment

Target 20–40 companies. Use these searches:

```
"[domain] startup [city]"
"[domain] company [city] Series B OR Series C"
"[domain] defense tech [city]"
crunchbase "[domain]" "[city]" funded 2023 OR 2024 OR 2025
```

Also use known lists (pick what fits the domain):
- For space/defense: SpaceNews company index, Defense News top 100
- For deep tech: YC company directory, a16z portfolio, Lux Capital portfolio
- For quantum/photonics: The Quantum Insider company list
- For IT/MSP: Channel Futures MSP 501, CRN MSP/solution-provider lists, regional MSP directories

**Resolve & record each company's hiring surface (build the *verified* target list).** For
each candidate company, resolve its ATS feed and persist it so this run and future sweeps hit
it directly:
1. Check whether it's already tracked: `python jobsdb.py company show --like <part>`.
2. Resolve its feed: `python ats_probe.py "<Company Name>"` → which platform/slug resolved
   + open-role count (eyeball the sample titles to reject a wrong-company slug collision).
3. Record the outcome on the company row (`ats_probe.py` prints the exact line):
   - resolved feed → `jobsdb.py company verify "<Company>" --status feed_verified
     --ats-platform <p> --ats-slug <s> --open-roles <n>`
   - careers page but no clean feed → `--status careers_only`
   - couldn't resolve (transient/unknown) → `--status unresolved` (recheck next run)
   - no hiring surface found at all → `--status unverified`
4. A relevant company with no current matching role still belongs on the list — register it
   with `jobsdb.py company add` as a `jobs=0` manual-monitor (completeness rule), not skipped.

This persisted, verified company list is what Phase 3a then sweeps for live roles.

### Step 2c: Flag Warm Paths
For each company, note:
- Any connection the candidate has (alumni, ex-colleague, recruiter)
- Whether the company is known to be actively hiring (recent funding, headcount signals)

### Step 2d: Flag multi-region companies

For companies with offices in multiple regions (e.g. a US HQ plus UK, Australia, or
Asia offices), flag them as **multi-region** in the company list. This signal is used
during Phase 4c (location match) — multi-region companies frequently post identical
JDs across regions under different ATS IDs, and aggregators only show one location.
Extra location verification is required for these companies.

---

## Phase 3: Multi-Source Role Discovery

Run sources **in the order listed below**. The company's own surface comes first; everything
else is fallback or supplemental sweep. Do not stop after the first few results — run
through the full hierarchy for breadth.

**Key principle: once a company's roles are verified live on the company surface in 3a,
do not re-search 3b–3f for that company.** The aggregator sweeps (3b–3f) exist to discover
roles at companies NOT yet on the target list, or as fallback when a company's own surface
is inaccessible. Re-searching aggregators for already-verified roles wastes cycles and risks
surfacing stale duplicates of the same posting.

### 3a: Company Careers Page (PRIMARY)

For every company on the target list (Phase 2), check the company's own careers page first.
This is the authoritative source. Anything found here is automatically verified live —
but location still must be verified separately in Phase 4c.

Attempt in this order:

1. **Direct fetch:** `web_fetch` on the company's careers URL
   - Common patterns: `[company].com/careers`, `[company].com/jobs`, `careers.[company].com`
2. **Site-restricted search:** if direct fetch fails (JS-blocked, redirect loop, etc.)
   ```
   site:[company].com careers
   site:[company].com jobs "[role keyword]"
   ```
3. **Company ATS subdomain:** if both above fail, check the company's ATS-hosted board.
   Most companies route their careers page to one of these:
   ```
   boards.greenhouse.io/[company]
   jobs.lever.co/[company]
   jobs.ashbyhq.com/[company]
   apply.workable.com/[company]
   [company].jobvite.com
   jobs.smartrecruiters.com/[company]
   ```
   ATS subdomains are the company's own posting source — treat as equivalent to the
   careers page for verification purposes.

4. **ATS public JSON API (PREFERRED when the board is JS-rendered):** modern ATS career
   pages are JavaScript-rendered, so a static `web_fetch` of the HTML board often returns
   only meta tags / a mission statement — no postings. Hit the board's public JSON API
   instead. It returns structured data with the **authoritative per-posting location**,
   which also satisfies Phase 4c. Known endpoints (slug = company's ATS slug):
   ```
   Greenhouse: https://boards-api.greenhouse.io/v1/boards/[slug]/jobs        (location.name + absolute_url + updated_at)
   Lever (US): https://api.lever.co/v0/postings/[slug]?mode=json             (categories.location, workplaceType, createdAt ms)
   Lever (EU): https://api.eu.lever.co/v0/postings/[slug]?mode=json          (some orgs are on the EU instance — try both)
   Ashby:      https://api.ashbyhq.com/posting-api/job-board/[slug]          (location, isRemote, publishedDate)
   Workable:   the documented board API is POST-only, BUT the widget account endpoint is a
               readable GET that returns the full list (title, location, workplace_type, shortcode):
               https://apply.workable.com/api/v1/widget/accounts/[slug]   (verified 2026-06-03)
               (www.workable.com/api/accounts/[slug] 302-redirects to it.) Fallback: mirror
               jobs.workable.com/view/[id]/[title]-in-[city]-at-[company] (the slug embeds the city)
   Freshteam:  careers.[company].com/jobs (readable HTML)  ·  Paycor: recruitingbypaycor.com career site (readable)
   Rippling:   https://api.rippling.com/platform/api/ats/v1/board/[slug]/jobs  (JSON list; UI at ats.rippling.com/[slug]/jobs)
               (verified 2026-06-04; several companies have migrated here off Greenhouse/Lever)
               (2026-06-08: each role's location is workLocation.label — NOT city/state/country fields; id=uuid)
   Comeet:     https://www.comeet.com/jobs/[slug]/[token]  (HTML; empty boards render a "no open positions" template — a 404 on a
               search-indexed job means the req closed, not a bad slug). Verified 2026-06-04.
   Jobvite:    https://jobs.jobvite.com/[slug]/jobs  (readable). Verified 2026-06-04: Uplight, Exabeam/LogRhythm.
   Workable v3: https://apply.workable.com/api/v3/accounts/[slug]/jobs  (paged via nextPage token; complements the v1 widget GET above).
   ```
   **Phenom-portal / gated-Workday employers:** some large enterprises route through a Phenom branded portal (jobs.[company].com)
   or a Workday tenant whose CXS endpoint bot-blocks (HTTP 422/403) — no clean public JSON. Verify on the branded careers page
   itself and tag the role `unverified` (not `verified`) until re-confirmed live.

   **`ats_probe.py` — the ATS Cookbook, automated.** Rather than hand-trying each endpoint, run
   `python ats_probe.py "<Company Name>"`: it derives candidate slugs from the name and probes
   Greenhouse, Lever (US+EU), Ashby, Workable, and Rippling, reporting which platform/slug
   resolved, the open-role count, and sample titles/locations. Workday is opt-in
   (`--workday-tenant/--workday-site/--workday-n`, since a bare slug can't address it). It prints
   a ready-to-paste `jobsdb.py company verify ...` line so the resolved feed is recorded on the
   company row (see Phase 2b). A guessed slug can resolve to a *different* company's board, so
   eyeball the sample titles before trusting a derived-slug hit; pass `--slug` when you know it.

   `createdAt` (Lever, epoch ms) and Greenhouse `updated_at` give the posting date for 4d.
   If `api.lever.co` 404s for a slug, the org is on the EU instance — use `api.eu.lever.co`.

   **Periodic fresh-scan sweep (catch NEW roles at companies already in the DB):** for a
   re-scan, script a sweep that hits every tracked company's JSON feed (Greenhouse/Lever/Ashby
   GET, Workday CXS POST), diffs incoming titles against the stored `dedup_key`s, and keeps
   only NET-NEW roles passing the level + function + location filters — far cheaper than
   re-fetching pages, and the feed location is already 4c-authoritative. Filter lessons
   (verified 2026-06-03): exclude over-leveled titles
   (`senior|sr|staff|principal|lead|manager|director|III|IV|postdoctoral`), and require an
   explicit **US token** for any "remote" or foreign-remote (e.g. Turkey/Mexico) leaks in as a
   false location match. A feed returning **0** vs. **erroring** are different — log the HTTP
   status so a dead feed reads as a blind spot, not an empty result.
   **ATS feeds drift — re-check slugs each sweep:** companies change platform on
   acquisition/region move (e.g. a US Lever org migrating to EU Lever, or a Greenhouse board
   token changing after an acquisition). When a feed 404s, find the new board rather than
   marking the company dead — `ats_probe.py` (see the ATS Cookbook note below) automates the
   re-resolve.
   **When a feed drifts, also fix the company ROW** so future sweeps hit the right endpoint
   instead of re-failing on the dead one. For an acquisition/rename, `jobsdb.py company
   rename --from "<old>" --to "<new>" --ats-slug <slug> --careers-url <url>` (renames in place,
   or merges if the new name already exists). `rename` carries name/slug/careers_url but has
   **no `--ats-platform` flag** — if the platform itself changed (e.g. lever→greenhouse),
   follow with `jobsdb.py company add --name "<new>" --ats-platform <platform>` (idempotent
   upsert; updates only the supplied non-empty field, never clobbers).
   (Worked examples of real drifts/acquisitions: `examples/quantum-field-notes.md`.)

   **Workday (large defense/space/enterprise — Maxar, Trimble, Sierra Space, Lockheed,
   NCAR/UCAR, etc.):** Workday boards are JS-rendered with NO Greenhouse-style GET feed,
   which used to be a verification blind spot. Use the **Workday CXS JSON endpoint** on the
   tenant host `[tenant].wd[N].myworkdayjobs.com`:
   ```
   List (POST):  /wday/cxs/[tenant]/[careerSite]/jobs
                 body {"limit":20,"offset":0,"searchText":"<keywords>","appliedFacets":{}}
                 headers: Content-Type AND Accept: application/json (some tenants 400 without Accept)
                 -> returns title, locationsText, externalPath, postedOn for each posting
                 -> limit MAX is 20 (limit>20 -> HTTP 400); paginate with offset 0,20,40...
                 -> reqid = trailing _R##### of externalPath; dedup_key = workday:{tenant}:{reqid} lowercased
   Detail (GET): /wday/cxs/[tenant]/[careerSite]/job/[externalPath]
                 -> full posting incl. exact location + datePosted (use to confirm one role live)
   ```
   **(2026-06-08 sweep corrections — these silently corrupt a sweep if missed):**
   - The human-facing posting URL is `[host]/[careerSite][externalPath]` — `externalPath` itself
     OMITS the careersite segment, so `host+externalPath` 404s. Always insert `/[careerSite]`.
   - The CXS `title` field sometimes DROPS the seniority that is present in the `externalPath`
     slug (e.g. title "Software Development Engineer" but path `_Senior-Software-Development-...`).
     Run the over-level filter against the path slug too, or a Senior role slips through as entry.
   - **Workable dedup keys are lowercased** (`workable:{slug}:{shortcode}.lower()`) — the widget API
     returns shortcodes UPPERCASE; forgetting `.lower()` makes every existing role read as
     "expired" and re-inserts a duplicate. (Greenhouse numeric ids / Lever UUIDs are case-stable.)
   The GET job-detail endpoint is the reliable way to confirm a specific Workday role's
   location and live status for Phase 4c. Some tenants expose multiple career sites (e.g.
   Maxar's public board 403'd but its `Cleared_Opportunities` site verified) — try the
   site name from the careers-page URL. Note many defense/space Workday roles carry a
   clearance/citizenship gate — capture it as a screening risk.

   **Re-verification caveat (sweep Part 0) — presence is reliable, absence is NOT:** a role
   *appearing* in a feed proves it live, but a role *missing* only proves it gone when the
   feed was fetched COMPLETELY. Greenhouse/Lever/Ashby/Workable return the whole list in one
   call (safe to expire on absence). Workday CXS paginates (limit 20) and some tenants return
   only a capped/default subset for an empty `searchText` (a big tenant answering `total:40`
   is the tell) — so **never auto-expire a Workday role on sweep-absence**; confirm via the
   GET job-detail endpoint (200=live, 404=gone) first. Also reqid schemes vary — UCAR uses
   `REQ-2026-49-#`, not `R#####` — so matching a stored `ats_job_id` against parsed feed ids
   can false-flag "gone". The detail GET is the tiebreak. (2026-06-04 sweep: this caught 2
   false-gones — UCAR + NLR roles were live the whole time.)

   **National labs, universities & research institutions — DO NOT assume USAJOBS.** Most
   run their OWN career site (frequently Workday or Taleo) and must be swept there, not
   skipped as federal aggregators. When a Workday list endpoint 404s, the careersite *name*
   is usually wrong — derive the right one from the org's careers landing page rather than
   assuming it matches a stored URL slug. Watch for renames/acquisitions (a lab or division
   can change names while keeping the same Workday tenant, so the dedup_key tenant is stable
   even when the careersite path moves). The genuine exception is true **federal civilian**
   roles (e.g. NIST), which do post on **USAJOBS.gov** (citizenship gate, slow). Many
   defense/space lab roles carry a clearance/citizenship gate — capture it as a screening risk.
   (Worked CO-lab examples — NLR/NREL, NCAR/UCAR, SwRI, LASP — are in
   `examples/quantum-field-notes.md`.)

   **Big-tech embedded-data boards (Google, etc.):** some large employers run no public
   ATS feed at all — Google's careers site is JS-rendered and its legacy JSON API
   (`careers.google.com/api/v3`) is **dead (404)**. But the results page server-embeds the
   full job data in a JS callback: `AF_initDataCallback({key:'ds:1', ... data:[...]})`.
   Fetch the HTML, pull the `ds:1` block's `data` array, and read each job record
   (`data[0][i]`): `[0]`=id, `[1]`=title, `[4][1]`=min-qualifications HTML (degree level),
   `[9]`=locations (each `[0]`=display, `[2]`=city, `[4]`=state code). Presence in the feed
   = live (satisfies 4c/4d); the per-location `state` field is the authoritative location.
   Helper: `python google_careers.py "<query>" --state <ST> [--json]` does the fetch+parse and
   tags each role's degree level (so over-leveled roles are obvious at a glance).

   **Amazon (custom public API):** no ATS feed, but `https://www.amazon.jobs/en/search.json`
   is a readable JSON endpoint. Gotchas (2026-06-08): it only honors `base_query` + `country`
   server-side — `loc_query`/state params are IGNORED (request echo shows `location:null`), so
   **paginate via `offset` and filter by state CLIENT-SIDE**. The per-job `state` field is the
   **2-letter code** (`CO`, not `Colorado`) — filtering on the full name silently returns 0.
   Helper: `python amazon_jobs.py "<query>" --state CO [--json --max-pages N]` (paginates +
   filters + tags level/intern/new-grad). Present in feed = live (satisfies 4c/4d).

   **Microsoft (custom API — BLOCKED from stdlib here):** the real endpoint is
   `https://gcsservices.careers.microsoft.com/search/api/v1/search?q=<kw>&lc=<loc>&pg=1&pgSz=20`
   (results under `operationResult.result.jobs[]`, apply URL `jobs.careers.microsoft.com/global/en/job/<jobId>`).
   But that host is behind a WAF that serves an **invalid/empty TLS cert** to non-browser clients
   (`SSL: CERTIFICATE_VERIFY_FAILED`, empty SAN) — the UI hosts (`jobs.careers.microsoft.com`) TLS
   fine but are JS-rendered. So there is **no clean stdlib puller from this environment**; Microsoft
   stays a `careers_only` monitor. Revisit from a browser-context fetch or if the WAF behavior changes.

**Important for multi-region companies (flagged in Phase 2d):** the same role title and
JD shell often exists as separate ATS IDs per region. When pulling a multi-region
company's roles, capture every ATS ID for that title and check the location field on
each one. Do not assume a single posting represents all regional variants.

If any of the three attempts succeed, mark every role found ✅ verified live on the
company surface, capture URLs and posting dates, and **do not run 3b–3f sweeps for that
company**. Move to the next company.

If all three attempts fail, mark the company as "career page inaccessible" and proceed
to 3b–3f for that company's roles, knowing they will be tagged ⚠️ Unverified.

### 3b: ATS Portal Sweep (broad fallback / discovery)

These find roles at companies not on the target list, and serve as fallback when 3a fails.
Roles found here that are NOT on a known company's ATS subdomain require verification in
Phase 4 before being reported as Tier 1 or Tier 2.

```
site:greenhouse.io "[domain keyword]" "[location]"
site:lever.co "[domain keyword]" "[location]"
site:workable.com "[domain keyword]"
site:jobvite.com "[domain keyword]" "[location]"
site:jobs.ashbyhq.com "[domain keyword]"
site:apply.workable.com "[domain keyword]"
site:jobs.smartrecruiters.com "[domain keyword]"
```

### 3c: LinkedIn Jobs (supplemental)
Skip for any company already verified in 3a.
```
"[role title]" "[city]" site:linkedin.com/jobs
"[role title]" "[city OR remote]" "[domain keyword]" site:linkedin.com
```

### 3d: Google Jobs / Indeed (aggregator sweep)

Aggregators are useful for breadth but lag significantly and frequently retain expired
postings. Treat as discovery only — every role found here MUST be verified against the
company surface in Phase 4 before being reported as Tier 1 or Tier 2. Skip for any company
already verified in 3a.

**Critical aggregator warning:** Builtin, Glassdoor, careerbliss, ZipRecruiter, and
similar sites often cross-post a single ATS ID across multiple regional pages and
display only one location label. The actual location is on the company ATS, not the
aggregator. Never trust aggregator location fields.

```
"[role title]" jobs "[city]" [current year]
"[role title]" "[domain]" [state] jobs
"[role title]" remote "[domain]"
site:indeed.com "[role title]" "[city]"
"[domain keyword]" engineer "[city]" site:indeed.com
```

### 3e: Domain-Specific Boards (fallback)

Use the reference file to select the right boards for the candidate's domain.
These are fallbacks — same verification requirement as 3d applies. Skip for any company
already verified in 3a.
See: `domain-boards.md`

### 3f: Funding Signal Search
Recently funded companies are actively hiring but often haven't posted yet.
```
"[domain]" startup "[city]" funding [current year]
"[domain]" "series B" OR "series C" "[city]" [current year]
crunchbase "[domain]" "[city]" recent funding
```
Funding signals feed back into Phase 2 — add newly-discovered companies to the target
list and re-run 3a for them.

---

## Phase 4: Verification, Date Anchoring & Location Match

Every role found in Phase 3 must pass through this phase before being tiered. Location
match (4c) is a mandatory hard gate — roles failing 4c are excluded from Tier 1 and
Tier 2 regardless of how strong the technical fit is.

### 4a: Anchor today's date
Record today's date as the reference point for all "days since posted" calculations.
This is the only correct way to evaluate posting freshness.

### 4b: Verify each role is live

For every role NOT found directly on the company's careers page or ATS subdomain in 3a,
attempt URL verification in this order:

1. **Try the company careers page directly** (`web_fetch` on `[company].com/careers` or
   the equivalent)
2. **Try `site:[company].com/careers` search**
3. **Try the company's ATS subdomain** (Greenhouse, Lever, Ashby, Workable, Jobvite,
   SmartRecruiters — see 3a step 3 for URL patterns)

If the role appears on any of these, the URL is confirmed live.
If none of the three work but the role appears on a major ATS aggregator with a recent
post date, the URL is "aggregator only."
If the career page is inaccessible AND the posting date cannot be determined, the URL
is "unverified."

### 4c: Verify the role's location matches the candidate's constraint (MANDATORY)

**This step is mandatory and is a hard gate.** A live URL is not enough. The role must
also be in a location the candidate can actually work.

Steps:

1. **Pull the location DIRECTLY from the company ATS** — never from aggregator location
   fields. Workable, Greenhouse, Lever, and Ashby all include a "Location" field on the
   job page; ATS pages can be JS-rendered, so if static `web_fetch` returns only meta
   tags, fall back to (in order):
   - **The ATS public JSON API** (see 3a step 4) — the most reliable: it returns the exact
     location string per posting (e.g. Lever `categories.location` + `workplaceType`,
     Greenhouse `location.name`). This is how the multi-region case is resolved cleanly.
   - The mirror URL slug (e.g. Workable's `jobs.workable.com/view/.../[role-title]-in-[city]-at-[company]` — the city is in the slug)
   - Site-restricted search for the role title plus city names
   - Reading the JD body for office/location language
2. **Compare against the candidate's stored location constraint** (from Phase 1a memory
   or Phase 1b extraction).
3. **For "remote" roles, require explicit confirmation in the JD body.** Acceptable
   phrasing: "Full-time remote," "100% remote," "fully remote," "remote (US)," "work
   from anywhere in [region]," or an explicit "Ability to Work Remotely" field set to
   full or part-time remote. NOT acceptable as confirmation: "remote-eligible" without
   detail, "may be remote," "hybrid with flexibility," or aggregator-set "Remote" tags
   that don't appear in the actual JD.
4. **For multi-region companies (flagged in Phase 2d), verify the specific ATS ID is
   the candidate's-region variant.** If the same role title exists as multiple ATS IDs,
   each ID may correspond to a different office, with different salary ranges and
   work-authorization requirements.

### 4d: Capture posting date

Record the posting date for every role when visible on the source. Common locations:
- ATS pages usually show "Posted X days ago" or an explicit date
- Aggregator listings often show "Posted N days ago"
- Some company pages list dates in the URL or job ID metadata
- LinkedIn shows relative dates ("2 weeks ago")

If no date is visible anywhere, record "Unknown."

### 4e: Apply verification tags

Every role gets one of FOUR tags going forward:

| Tag | Meaning |
|-----|---------|
| ✅ Verified live & location match | URL live on company ATS AND location matches candidate constraint |
| ❌ Wrong location | URL is live, but location does not match candidate constraint (auto-excluded from Tier 1 and Tier 2) |
| ⚠️ Aggregator only | Confirmed posted on an aggregator/job board, but NOT confirmed live on the company's surface (may be stale). Location must still be verified per 4c if reported. |
| ⚠️ Unverified | Posting found but no source could be confirmed live; or career page is inaccessible |

---

## Phase 5: Tiering & Fit Assessment

For each role with the ✅ Verified live & location match tag, assess:

| Factor | Questions to ask |
|--------|-----------------|
| **Technical fit** | Does the JD match the candidate's actual experience? |
| **Level fit** | Is the seniority correct? (over/under-leveled = screen risk) |
| **Screening risks** | Any hard requirements the candidate can't meet? |
| **Warm path** | Is there a referral, contact, or recruiter path? |
| **Comp signal** | Is the range stated or estimable? Does it meet target? |
| **Citizenship/clearance** | Does the candidate meet citizenship and clearance requirements? |

### Tier Definitions
- **Tier 1**: Strong fit on 4+ factors, apply immediately
- **Tier 2**: Strong fit on 2–3 factors, worth pursuing with tailoring
- **Tier 3**: Partial fit or uncertain, monitor or opportunistic apply

### Location-mismatch is automatic exclusion

Roles with the ❌ Wrong location tag are **NEVER assigned Tier 1 or Tier 2**, regardless
of how strong the technical fit otherwise is. They appear only in an "Excluded — Wrong
Location" section of the report, with the exclusion reason documented so the candidate
can verify the decision.

This is non-negotiable. The point of the location constraint is to save the candidate
from spending tailoring cycles on a role they cannot accept. A "strong fit but wrong
location" Tier 1 entry is a failure of the system.

### Sort order within each tier
1. ✅ Verified live & location match, **oldest posting date first** — older roles are
   more likely to still be open and reviewing applications. Recruiter attention per
   applicant tends to be higher on aging reqs.
2. ✅ Verified live & location match, newer postings next
3. ⚠️ Aggregator only — sorted to the bottom of the tier (must still pass location 4c)
4. ⚠️ Unverified — sorted to the very bottom

---

## Phase 6: LinkedIn Contact Search (Tier 1 roles only)

After completing the role list, automatically run a LinkedIn contact search
for every Tier 1 role before persisting to the database (Phase 7). Attach the contacts to
their job in the scan batch file (the per-job `contacts` array).

For each Tier 1 role, read linkedin-outreach.md and follow its contact search
process. Find:
- The person who posted the job (if identifiable)
- Hiring manager or team lead for the specific role
- Internal recruiter at the company
- Any alumni or shared background hooks

Return results per company in this format:

**[Company Name] — [Role Title]**

| Priority | Name (if found) | Title | Hook | Action |
|----------|----------------|-------|------|--------|

If a specific name cannot be confirmed, list the contact type and note it
was not confirmed — do not invent names.

---

## Phase 7: Persist to Database

The job list is stored in the database, not generated as a document. Read `database.md`
for the schema, the dedup-key rule, and the scan batch format (`job_scans/*.json`).

### 7a: Build the dedup key for every role

Every role gets a deterministic `dedup_key` so the same posting is never stored twice
across runs (see `database.md`):
- ATS platform + job id → `"{platform}:{slug}:{job_id}"` (preferred)
- Company page, no clean id → `"site:{domain}:{slug-of-title}"`
- Aggregator-only → `"agg:{sha1(company|title|location)[:12]}"`

### 7b: Assemble the batch and upsert

Write a single scan batch file into the **`job_scans/`** folder, named
`YYYY-MM-DD[_label].json` (e.g. `job_scans/2026-05-31_swe.json` — add a short label if
you run more than one scan in a day). It contains **every** role found — Tier 1/2/3, plus
`wrong_location` and `unverified` ones (they're stored, they just aren't tiered). Each job
carries its `verification_tag`, `tier`, `location`, `location_match`, `category_label`,
posting date, comp, fit summary, screening risks, and (for Tier 1) its `contacts` array.
These files are the dated audit trail of every scan.

```
python jobsdb.py upsert-batch job_scans/YYYY-MM-DD[_label].json
```

The upsert deduplicates against prior runs, refreshes `last_seen` and metadata on
already-seen roles, inserts genuinely-new roles as `status='new'`, and **preserves any
`applied`/`ignored`/`rejected` status** so a re-run updates the pipeline rather than
recreating it. It returns a run summary (found / new / updated) used in Phase 8.

### 7c: Present from the database (chat, not a document)

Surface the results by querying the DB — this replaces the old report document:

```
python jobsdb.py stats --candidate <slug>
python jobsdb.py query --candidate <slug> --status new --format table
```

The structure below defines how to organize that chat presentation (and the optional
`jobsdb.py export` snapshot in CSV/Markdown/.docx, if the user asks). It is no longer a
mandatory .docx.

### Candidate Brief
[Summary of extracted profile, including the location constraint as confirmed from the DB or user]

---

### 🔴 Tier 1 — Apply Immediately

| Company | Role | Location | Comp | Date Posted | Source | Why it fits | Screening risks |
|---------|------|----------|------|-------------|--------|-------------|-----------------|

The **Source** column contains the verification tag AND a direct URL the user can click
to confirm the posting themselves. Example values:
- `✅ Verified live & location match — boards.greenhouse.io/infleqtion/jobs/12345`
- `⚠️ Aggregator only — apsphysicsjobs.com/job/30405` (location verified per 4c)
- `⚠️ Unverified — linkedin.com/jobs/view/12345`

The **Location** column must include the actual city/state from the company ATS, not
the aggregator label.

---

### LinkedIn Contacts — Tier 1 Roles
[Contact table per company, as defined in Phase 6]

---

### 🟡 Tier 2 — Strong Fit, Pursue Actively

| Company | Role | Location | Comp | Date Posted | Source | Why it fits | Notes |
|---------|------|----------|------|-------------|--------|-------------|-------|

---

### 🟢 Tier 3 — Monitor / Opportunistic

| Company | Role | Location | Date Posted | Source | Notes |
|---------|------|----------|-------------|--------|-------|

---

### ❌ Excluded — Wrong Location

This section is required when any roles failed the Phase 4c location match. List each
excluded role with its actual location and the reason for exclusion. Do NOT bury these
silently — surface them so the candidate can verify the location determination was
correct.

| Company | Role | Actual Location | Why excluded | Source |
|---------|------|-----------------|--------------|--------|

---

### Funding Signals
[Companies recently funded that may be hiring but not yet posted]

### Next Steps
[Prioritized action sequence: who to contact first, what to apply to first]

**Always include this reminder in the Next Steps section:**
> "Before submitting any application, re-check the Source URL — even ✅ verified-live
> postings can be pulled between report date and application date. The older the report,
> the more important this re-check becomes."

---

## Phase 8: Chat Delivery

When presenting results in chat (after persisting to the DB in Phase 7), always state the
run summary and verification breakdown explicitly. Include the `upsert-batch` run summary
(found / new / updated / expired), then:

1. **Location-match breakdown:** how many roles passed 4c vs were excluded. Example:
   > "Found 22 verified-live roles across the target companies; 14 passed the location
   > match (CO or remote), 8 were excluded as wrong-location. The 8 are listed in the
   > 'Excluded — Wrong Location' section for transparency."

2. **Verification breakdown by tag:**
   > "Tier 1 has 5 roles: 3 ✅ verified live & location match, 2 ⚠️ aggregator-only
   > (location confirmed via mirror URL). Tier 2 has 7 roles: 4 verified, 3 aggregator."

3. **Multi-region warnings:** if any companies were flagged multi-region in Phase 2d
   and produced location-excluded roles, name them explicitly:
   > "Heads up: Infleqtion has offices in CO, IL, WI, AU, and UK. The 'Algorithms &
   > Applications' role under Workable ID 484720A3C0 is the UK Kidlington/Harwell
   > variant — not Colorado. Excluded."

4. **Aggregator-only ratio warning:** if >40% of Tier 1 + Tier 2 are aggregator-only,
   call it out as a quality concern.

The user should not have to read the Source or Excluded columns to learn how much of
the report is trustworthy or how the location filter performed. Surface it up front.

---

## Rules & Guardrails

- **Every stored job must have a `dedup_key` and a `verification_tag`.** The dedup key is
  what prevents duplicate rows across runs — never persist a job without one.
- **Never overwrite a terminal status.** `upsert-batch` must not reset an `applied`,
  `ignored`, or `rejected` job back to `new`/`active` — only refresh its metadata.
- **Never include a Tier 1 or Tier 2 role without a source URL** the user can click to
  verify. The `url` field is mandatory and must contain a working link.
- **Never report a role as Tier 1 or Tier 2 without attempting verification** through
  the three-step fallback in Phase 4b. Skipping verification is the failure mode this
  workflow exists to prevent.
- **`verified` requires posting-level proof, not company-level.** Tag a role `verified`
  ONLY when its **exact posting URL returned 200** OR it appeared in a fully-pulled ATS JSON
  feed carrying that posting's authoritative apply URL. A resolvable *company feed/careers
  page*, or a role seen only in a search-engine snippet, is company-level evidence — tag
  those roles `aggregator` or `unverified`, never `verified`. **Never construct, guess, or
  infer a posting URL or ATS job-id** — if you didn't read it from the live posting/feed,
  you don't have it. (Real failure, 2026-06-07 rebuild: a discovery lane that couldn't reach
  several Lever/Workday feeds reported roles from snippets as `verified` with inferred UUIDs;
  ~7/72 links 404'd, and two "roles" did not exist in the live feed at all. Company-level
  `feed_verified` ≠ posting-level `verified`.)
- **Never assign a Tier to a role that has not passed Phase 4c location match.** Wrong
  location is auto-excluded — there is no override.
- **Never trust aggregator location fields.** Workable, Greenhouse, Lever, Ashby ATS
  pages are the source of truth. Builtin, Glassdoor, ZipRecruiter, careerbliss, and
  similar mirrors lie about location regularly because they cross-post a single ATS ID
  across regional pages.
- **For multi-region companies, every ATS ID matters.** Do not assume a role with a
  given title is in the candidate's region just because the company is HQ'd there. Pull
  the per-ID location.
- **"Remote" must be confirmed in the JD body, not inferred.** "Remote-eligible" or
  "may be remote" without further detail is not confirmation.
- **Minimum 15 roles total, with at least 8 ✅ verified live & location match across all
  tiers.** If fewer verified-live-and-matching roles exist after a thorough search,
  report that fact honestly in the chat delivery rather than padding the report with
  aggregator-only listings or wrong-location stretches. The 15-role floor should never
  compromise verification or location standards.
- **Flag comp mismatches explicitly** — don't bury a role with a $90K ceiling when the
  candidate targets $200K.
- **Flag hard screening risks** — Zemax/Code V, active clearance required, specific tools
  listed as mandatory, citizenship requirements. Don't let candidate waste time on
  guaranteed filters.
- **Don't conflate levels** — a Senior role for a Staff/Principal candidate is a step
  down; note it.
- **Warm paths change sequencing** — a role with a referral path should always be Tier 1
  regardless of fit score, and outreach should happen before application.
- **Aggregator-only roles never go above verified roles** in tier sorting, even if the
  fit is better.
- **Always remind the user to re-verify before applying** — include the re-check
  reminder in the Next Steps section of every report.

---

## Notes on Search Depth

The goal is to surface roles the candidate would NOT find with a standard LinkedIn search,
AND to confirm those roles are actually still open AND in a location the candidate can
work, before recommending them. Prioritize:

1. **Company careers pages and ATS subdomains** — the authoritative source for whether a
   role is currently being recruited AND where it's located
2. **Funding-stage companies** — hiring intent before postings exist
3. **ATS portal sweeps** — most underused source for hidden roles at companies not yet on
   the target list
4. **Google Jobs / aggregators** — useful for discovery, but always verify URL AND
   location before reporting

A thorough run should involve **15–25 distinct searches** minimum, plus a verification
pass against the company surface for every aggregator-discovered role, plus a location
match check for every role that survives URL verification. Do not stop early. Once a
company's roles are confirmed live AND location-matched on its own surface, do not
re-search aggregators for that company — move to the next company.
