# Job Pipeline Database — Contract

This file is the contract between Claude and the local job database. It defines the
schema, the `jobsdb.py` CLI surface, and the JSON format Claude writes after a search.
Read this before persisting search results or querying the pipeline.

The database (`jobs.db`) is the single source of truth for the job list. It is created
and modified **only** through `jobsdb.py` — never hand-edit it, and never write a job
document as a substitute for storing the job.

---

## Schema (6 tables)

### `candidates` — identity, extracted from a resume
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| slug | TEXT UNIQUE | e.g. `example_candidate`; used in folder paths |
| name | TEXT | |
| email | TEXT | |
| location_constraint | TEXT | e.g. "Colorado-based or fully remote only, no relocation" |
| citizenship | TEXT | |
| clearance | TEXT | e.g. "previously held TS, eligible for reinstatement" |
| comp_floor | INTEGER | annual USD, nullable |
| comp_target | INTEGER | annual USD, nullable |
| resume_path | TEXT | path to base resume |
| notes | TEXT | |
| created_at / updated_at | TEXT | ISO 8601 |

### `candidate_categories` — ranked industry/role preferences (drives the search)
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| candidate_id | INTEGER FK | → candidates(id), ON DELETE CASCADE |
| rank | INTEGER | **1 = highest priority** |
| label | TEXT | e.g. "Quantum software/computing/tech" |
| keywords | TEXT | comma-separated search terms for this bucket |
| | | UNIQUE(candidate_id, label) |

Example categories (illustrative — each candidate defines their own):
| rank | label | keywords |
|------|-------|----------|
| 1 | Quantum software/computing/tech | quantum software, quantum computing, qiskit, cirq, quantum SDK |
| 2 | Quantum-adjacent software | quantum sensing software, photonics software, scientific computing |
| 3 | General SWE / AI | software engineer, backend, ML engineer, AI engineer |

### `companies` — target-list companies
Global (not candidate-scoped) — under one-DB-per-person each user has their own.
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| name | TEXT UNIQUE | |
| careers_url | TEXT | |
| ats_platform | TEXT | greenhouse \| lever \| ashby \| workable \| jobvite \| smartrecruiters \| other |
| ats_slug | TEXT | the company's slug on that ATS |
| multi_region | INTEGER | 0/1 — flagged in SKILL Phase 2d |
| warm_path | TEXT | referral/contact note |
| notes | TEXT | |
| verification_status | TEXT | feed_verified \| careers_only \| unresolved \| unverified — company-level verification, set via `company verify` (the analog of a job's `verification_tag`) |
| last_verified | TEXT | ISO date the company's hiring surface was last checked |
| open_roles | INTEGER | open-role count from the last `ats_probe` (nullable; NULL = unknown) |

> These three columns are added to a **pre-existing** `jobs.db` automatically: `jobsdb.py`'s
> `connect()` runs an idempotent `_migrate()` (ALTER TABLE guarded by `PRAGMA table_info`),
> since `init` skips a populated DB. Fresh DBs get them from `schema.sql`.

### `jobs` — one row per posting (the core table)
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| candidate_id | INTEGER FK | → candidates(id), ON DELETE CASCADE |
| company_id | INTEGER FK | → companies(id), nullable |
| dedup_key | TEXT | canonical key, see below |
| title | TEXT | |
| url | TEXT | clickable source URL |
| ats_platform | TEXT | |
| ats_job_id | TEXT | |
| location | TEXT | **actual** city/state from the ATS, not aggregator label |
| remote_type | TEXT | onsite \| hybrid \| remote \| unknown |
| location_match | INTEGER | 0/1 — passed SKILL Phase 4c |
| comp_min / comp_max | INTEGER | annual USD, nullable |
| posting_date | TEXT | ISO 8601 or NULL ("Unknown") |
| verification_tag | TEXT | verified \| wrong_location \| aggregator \| unverified |
| tier | INTEGER | 1 \| 2 \| 3 \| NULL |
| category_label | TEXT | which `candidate_categories.label` bucket |
| fit_summary | TEXT | "why it fits" |
| screening_risks | TEXT | |
| status | TEXT | new \| active \| applied \| expired \| rejected \| ignored (default `new`) |
| first_seen | TEXT | ISO date the row was first inserted |
| last_seen | TEXT | ISO date last surfaced by a search |
| last_verified | TEXT | ISO date the URL was last confirmed live |
| applied_date | TEXT | nullable |
| resume_path | TEXT | tailored resume .docx, set via `mark` |
| cover_letter_path | TEXT | cover letter .docx, set via `mark` |
| notes | TEXT | |
| | | **UNIQUE(candidate_id, dedup_key)** |

### `contacts` — LinkedIn contacts (Tier 1 roles)
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| job_id | INTEGER FK | → jobs(id), ON DELETE CASCADE |
| name | TEXT | nullable — never invent |
| title | TEXT | |
| priority | TEXT | `★★★` \| `★★` \| `★` |
| contact_type | TEXT | hiring manager / recruiter / team lead / alumni |
| hook | TEXT | |
| action | TEXT | recommended action |
| confirmed | INTEGER | 0/1 — name actually confirmed vs. type only |
| notes | TEXT | |

### `search_runs` — log of each search (for stats/history)
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| candidate_id | INTEGER FK | |
| run_date | TEXT | ISO date |
| num_found / num_new / num_updated / num_expired | INTEGER | |
| notes | TEXT | |

---

## Dedup key rule (critical)

The `dedup_key` is what prevents duplicate rows for the same posting across searches.
Build it deterministically:

1. **Has an ATS platform + job id** → `"{platform}:{slug}:{job_id}"`, lowercased.
   - e.g. `greenhouse:infleqtion:12345`, `lever:psiquantum:abc-def`
2. **Company careers page, no clean ATS id** → `"site:{domain}:{slug-of-title}"`.
   - e.g. `site:infleqtion.com:quantum-software-engineer`
3. **Aggregator-only, no company surface** → `"agg:{sha1(company|title|location)[:12]}"`.

The same posting must always produce the same key. When in doubt, prefer the ATS-based
key — that is the company's authoritative identifier.

---

## `jobsdb.py` CLI surface

```
python jobsdb.py init
    Create jobs.db from schema.sql (idempotent; refuses to clobber data without --force).

python jobsdb.py candidate add --resume <path> [--slug <slug>] [--field key=value ...]
    Register or update a candidate. Claude extracts identity from the resume and passes
    fields (name, email, location_constraint, citizenship, clearance, comp_floor,
    comp_target). Matching is by slug — re-running with the same slug updates, never
    duplicates. (Slug defaults to a slugified `name` when `--slug` is omitted.)

python jobsdb.py candidate list
python jobsdb.py candidate show --slug <slug>

python jobsdb.py category set --candidate <slug> --json <categories.json>
    Replace the candidate's ranked category list (rank/label/keywords).

python jobsdb.py company list
    List all companies with job counts.
python jobsdb.py company show <name> | --like <substr>
    Inspect a company by exact name (full record + verification fields + job count), or
    search with --like (case-insensitive substring) when you don't know the exact name.
    Exact-name not-found exits non-zero and suggests --like.
python jobsdb.py company add --name <name> [--careers-url --ats-platform --ats-slug
    --multi-region --warm-path --notes]
    Register a target-list company without needing a job (idempotent; fills blanks, never
    clobbers). Use for `jobs=0` manual-monitors (completeness rule).
python jobsdb.py company verify <name> --status feed_verified|careers_only|unresolved|unverified
    [--date <ISO>] [--open-roles N] [--ats-platform P] [--ats-slug S] [--careers-url U] [--note T]
    Record a company-level verification outcome — the analog of `mark --verified` for a job.
    Create-or-update (the probe->verify path often meets a company not yet in the DB);
    --status is required. Feed/identity fields are sticky (filled, never clobbered); the
    verification state is overwritten; --note appends a dated line. The companion resolver
    `python ats_probe.py "<name>"` (stdlib) probes the known ATS feeds and prints the exact
    `company verify` line to paste.
python jobsdb.py company rename --from <old> --to <new> [--careers-url --ats-slug]
    Rename a company in place, or MERGE into the target if the new name already exists
    (repoints jobs, folds in missing fields, drops the duplicate row).

python jobsdb.py upsert-batch <job_scans/YYYY-MM-DD[_label].json>
    Insert new jobs / update existing ones for one candidate in a single transaction.
    Returns a summary: {found, new, updated}. Logs a search_runs row. (Expirations are
    handled separately by `reverify`/`mark`, not by upsert — see below.)
    Convention: write each scan's batch file into the `job_scans/` folder, named
    `YYYY-MM-DD.json` (add a short `_label` suffix if you run more than one scan in a day,
    e.g. `2026-05-31_quantum.json`). These files are the dated audit trail of every scan.

python jobsdb.py query [filters...]
    --candidate <slug>   --category <substring>   --tier 1|2|3
    --status new|active|applied|expired|rejected|ignored   --verification verified|...
    --location-match yes|no   --since <ISO date>   --limit N   --all   --format table|json
    By default shows only the live/actionable pipeline (new/active/applied); expired,
    rejected, and ignored are hidden. Pass --all to include them, or --status <x> to
    target one explicitly.
    Default sort: tier asc, then verified-live oldest-posting first (per SKILL Phase 5).
    Table output includes a `verif` column = age since last live-check (today / Nd /
    never); a trailing `!` flags never-verified or >7 days old — re-verify before applying.

python jobsdb.py stats --candidate <slug>
    Pipeline breakdown: counts by tier, status, verification_tag, location-match.

python jobsdb.py reverify list --candidate <slug> [--stale-days 2]
    Emit live (new/active) jobs due for re-verification: last_verified older than
    --stale-days (default 2), never verified, OR Tier 1/2 not yet re-checked today
    (Tier 1/2 are kept as fresh as each sweep allows, since they're the roles the
    candidate actually acts on). Claude re-fetches each URL, then records the outcome
    with `mark`. NOTE: last_verified is a snapshot, never a live guarantee — the binding
    freshness check is the per-role re-verify right before applying (and before
    resume/cover work, per those skills' Phase 0). Pass --stale-days 0 to force a full
    re-check of every live role.

python jobsdb.py mark <job_id> [--status ...] [--verified] [--resume <path>]
    [--cover <path>] [--applied-date <ISO>] [--note "..."]
    Update one job: status transition, refresh last_verified (--verified), attach
    generated document paths, log notes.

python jobsdb.py export --candidate <slug> [query filters] --format csv|md|xlsx|docx|all [--out <path>]
    Optional. Generate a report snapshot FROM the DB (not the source of truth).
    Default output dir: exports/<slug>_pipeline_<date>.<ext>. Accepts the same filters as
    `query` (--tier/--status/--category/--verification/--location-match/--since).
    - csv  : flat, one row per job keyed by dedup_key/job_id — stdlib `csv`, no deps.
    - md   : tiered Markdown report — stdlib, no deps.
    - xlsx : flat Excel workbook, same columns as csv, with rows color-coded by status
             (green=active, red=expired, amber=new, blue=applied, orange=rejected,
             grey=ignored), frozen header + autofilter. Native (stdlib `zipfile` writes the
             xlsx zip-of-XML) — NO dependency. This is the colored-columns view to hand a user.
    - docx : the original tiered, color-coded Word report — requires `python-docx`
             (imported lazily; if missing, prints an install hint and skips docx only).
    - all  : write csv + md + xlsx + docx.
    Same query filters as `query` select which jobs the snapshot contains — including the
    default hiding of expired/rejected/ignored (use --all for the full historical dump, or
    --status expired to export just the dead ones). So a default report never lists a
    pulled posting as a live Tier 1/2 role.
```

---

## Scan batch format (what Claude writes after a search)

Write this file into `job_scans/` as `YYYY-MM-DD[_label].json` (the dated audit trail of
each scan), then pass it to `upsert-batch`.

```json
{
  "candidate": "example_candidate",
  "run_date": "2026-05-31",
  "jobs": [
    {
      "company": "Infleqtion",
      "careers_url": "https://infleqtion.com/careers",
      "ats_platform": "greenhouse",
      "ats_slug": "infleqtion",
      "multi_region": true,
      "warm_path": "Ex-colleague Dana R. is a staff eng here — warm intro available",
      "dedup_key": "greenhouse:infleqtion:12345",
      "title": "Quantum Software Engineer",
      "url": "https://boards.greenhouse.io/infleqtion/jobs/12345",
      "ats_job_id": "12345",
      "location": "Boulder, CO",
      "remote_type": "hybrid",
      "location_match": true,
      "comp_min": 120000,
      "comp_max": 160000,
      "posting_date": "2026-05-10",
      "verification_tag": "verified",
      "tier": 1,
      "category_label": "Quantum software/computing/tech",
      "fit_summary": "Direct match: quantum SDK work, CO-based, level-appropriate.",
      "screening_risks": "Prefers PhD; candidate has MS — flag, not disqualifying.",
      "contacts": [
        {
          "name": null,
          "title": "Quantum Software Hiring Manager",
          "priority": "★★★",
          "contact_type": "hiring manager",
          "hook": "Posted the req on LinkedIn 2 weeks ago",
          "action": "Connect + short note before applying",
          "confirmed": 0
        }
      ]
    }
  ]
}
```

Rules for the batch:
- Every job MUST carry a `verification_tag` and a `dedup_key`.
- `location_match` must reflect SKILL Phase 4c — `wrong_location` tag ⇒ `location_match: false`
  ⇒ never tier 1/2.
- Omit `comp_min`/`comp_max`/`posting_date` (or use null) when genuinely unknown; do not guess.
- `contacts` is optional per job; populate for Tier 1 roles per `linkedin-outreach.md`.
- Company-level fields (`careers_url`, `ats_platform`, `ats_slug`, `multi_region`,
  `warm_path`) are read from the job and upserted onto the company. `warm_path` is the
  referral/contact note (SKILL Phase 2c) — supply it on any one job for that company.
  `multi_region` is sticky: once set true it is never cleared by a later scan that omits it.

---

## Upsert semantics (how `upsert-batch` decides insert vs. update)

Match each incoming job on `(candidate_id, dedup_key)`:

- **No match** → INSERT with `status='new'`, `first_seen = last_seen = run_date`,
  `last_verified = run_date` if `verification_tag` is `verified` OR `wrong_location`
  (both were confirmed live on the company surface) else null (`aggregator`/`unverified`
  were never company-confirmed, so they stay due for re-verification).
- **Match exists** → UPDATE `last_seen = run_date` and refresh metadata (tier, tag,
  location, comp, fit, posting_date). Refresh `last_verified` if newly verified.
  - **Preserve terminal status:** if existing `status` is `applied`, `ignored`, or
    `rejected`, do NOT change it. Only update metadata + `last_seen`.
  - A `new` job re-surfaced by any scan becomes `active` (it's been seen again). An
    `expired` job is revived to `active` **only** when it comes back with the `verified`
    tag — a mere `aggregator`/`unverified` re-sighting does not resurrect a dead posting.
    An already-`active` job stays `active`.

This is the mechanism that stops document regeneration and stale re-surfacing.
