# Job Pipeline DB — Project Plan

**Goal:** Replace the "regenerate a Word doc every search" workflow with a persistent
local SQLite database. The agent still performs the live search/verification (it must —
that part can't be a plain script), but results are stored, deduplicated, status-tracked,
and re-verifiable instead of thrown away each run.

**Environment:** Claude Code (CLI) on Windows. Python 3 (stdlib `sqlite3`, no external deps
required for the core). Working dir: `C:\Users\Austin\claude_jobs`.

---

## Problems this solves

| Old pain point | Root cause | Fix |
|----------------|------------|-----|
| Regenerates a new document every search | No persistence; each run starts blank | SQLite DB as single source of truth; reports are queries |
| Misses jobs / inconsistent coverage | No memory of what was already found | Dedup key + upsert; jobs accumulate across runs |
| Surfaces old/expired jobs | No re-verification of stored postings | `reverify` pass flips dead URLs to `expired` |

---

## Architecture (hybrid)

```
SEARCH (agent-driven)              MEMORY (Python + SQLite)
- web search / fetch        →      - dedup by stable key
- live verification (4b)    →      - status lifecycle
- location match (4c)       →      - re-verification
- tiering / fit (Phase 5)   →      - queryable pipeline
        |                                   |
        +-----> job_scans/<date>.json --> jobsdb.py upsert-batch --> jobs.db
```

Identity is **resume-keyed and multi-candidate**: running a search with a new resume
registers/updates that candidate and uses their constraints + ranked category preferences.

---

## File layout (target)

```
C:\Users\Austin\claude_jobs\
├── jobsdb.py              # CLI tool (built in Step 1–2)
├── schema.sql             # DB structure
├── jobs.db                # SQLite database (created by `init`; not hand-edited)
├── candidates/
│   └── <slug>/            # e.g. austin_long
│       ├── resume_base.docx
│       ├── resumes/       # tailored .docx
│       └── cover_letters/ # cover letter .docx
├── exports/               # optional report snapshots (csv/md/docx)
├── job_scans/             # dated scan batch files (audit trail): YYYY-MM-DD[_label].json
├── PROJECT_PLAN.md        # this file
├── database.md            # DB contract: schema + CLI usage  (Step 0)
├── Project_Instructions.md# orchestrator (revised Step 0)
├── SKILL.md               # search brain (revised Step 0)
├── resume-tailor.md       # per-role (revised Step 0)
├── cover-letter.md        # per-role (revised Step 0)
├── onboarding-questionnaire.md  # new-candidate screening questions (not in a resume)
├── linkedin-outreach.md   # unchanged
└── domain-boards.md       # unchanged
```

---

## Build steps & status

Legend: ☐ todo · ◐ in progress · ☑ done

### Step 0 — Documentation (do before any code)
- ☑ `PROJECT_PLAN.md` (this file)
- ☑ `database.md` — schema reference + CLI contract + JSON batch format
- ☑ Revise `Project_Instructions.md` — retarget Claude app → Claude Code + DB
- ☑ Revise `SKILL.md` — add Phase 7 (Persist to DB), dedup-key rule, candidate/category drivers
- ☑ Revise `resume-tailor.md` — pull role by job_id, write into candidate folder, record path
- ☑ Revise `cover-letter.md` — same DB integration

### Step 1 — DB foundation
- ☑ `schema.sql` — 6 tables (candidates, candidate_categories, companies, jobs, contacts, search_runs)
- ☑ `jobsdb.py` commands: `init`, `candidate add`, `candidate list/show`, `category set`,
  `upsert-batch`, `query`, `stats`
- ☑ Tested with hand-written sample batches — verified: dedup (supplied, computed, and
  agg-fallback keys), upsert preserves rows (7 not 10), new→active revival, metadata
  refresh on re-run, contacts persistence, category-priority query, Phase-5 sort order,
  search_runs logging
- ☑ Registered real candidate `austin_long` (from resume) + 3 ranked categories; test job
  data cleared, candidate/categories retained for the live run

### Step 2 — Re-verification & progress tracking
- ☑ `reverify list --candidate <slug> [--stale-days N]` — emits stale (new/active) jobs
  whose last_verified is old/null; no network I/O (agent fetches, then calls `mark`)
- ☑ `mark <id> --status ... --verified --resume <path> --cover <path> --applied-date
  <iso> --note "..."` — status transitions, last_verified refresh, doc paths, timestamped notes
- ☑ Tested: live/dead marking drops jobs off reverify list; new→active on --verified;
  applied sets applied_date; **terminal status (applied) preserved across re-upsert**
- ☑ Bug fixed during Step 2: `last_seen`/`last_verified` now move forward only (guard
  against replaying a back-dated scan batch)

### Regression suite — `test_jobsdb.py`
- ☑ 63-assertion suite driving the real CLI via subprocess against a throwaway DB
  (`JOBSDB_PATH` override). Covers init/idempotency, candidate parse+update, category
  replace, all three dedup-key paths, upsert update-not-dup, monotonic timestamps,
  every query filter + sort order, reverify staleness, all mark transitions, terminal
  status preservation, company warm_path/multi_region stickiness, and error handling.
  Run: `python test_jobsdb.py`. **63/63 pass.**

### Step 3 — Wire instructions to the DB end-to-end
- ☑ Audited every `jobsdb.py` reference across all `.md` files vs. the real CLI surface —
  all implemented commands/flags match exactly
- ☑ Documented `export` consistently across database.md / SKILL.md / Project_Instructions.md
  (now implemented in Step 5 — the docs describe the live command, not a stub)
- ☑ Dry-ran the documented orchestrator sequence (reverify list → write scan batch →
  upsert-batch → stats → query --status new) against the DB — runs clean end-to-end

### Step 4 — Live end-to-end  ☑
- ☑ Austin registered (resume) + 3 quantum-priority categories (done in Step 1)
- ☑ Ran a real rank-1 quantum search (CO + remote US). Pulled live roles from
  authoritative ATS APIs: Quantinuum (EU Lever), IonQ (Greenhouse), Infleqtion (Workable
  mirror). Persisted 8 real jobs — 7 location-matched, 1 wrong-location (Infleqtion UK
  Kidlington variant, the multi-region trap). Run artifacts: `job_scans/2026-05-31_*.json`.
- ☑ Verified correct tier/tag/location/dedup + Phase-5 sort on real data
- ☑ reverify loop confirmed on live data
- ☑ Refinement found via live run: `wrong_location` is live-confirmed too, so it now sets
  `last_verified` (won't loop in reverify); only `aggregator`/`unverified` stay due.
  Added regression assertions. Fixed Windows test-teardown file-lock (gc + tolerant remove).
- Note: real ATS pages are JS-rendered; the working pattern is their public JSON APIs
  (`api(.eu).lever.co/v0/postings/<slug>`, `boards-api.greenhouse.io/v1/boards/<slug>/jobs`,
  `api.ashbyhq.com/posting-api/job-board/<slug>`, Workable `jobs.workable.com/view/...`
  mirror whose slug embeds the city).
- Expanded sweep (later same day): 4 parallel discovery agents covered the CO quantum
  ecosystem + remote-US quantum + CO space/deep-tech + national labs + domain boards +
  LinkedIn + funding. Pipeline 21 -> 33. Key capability unlocked: **Workday CXS JSON**
  (`[tenant].wd[N].myworkdayjobs.com/wday/cxs/[tenant]/[site]/jobs` POST, `/job/[path]` GET)
  — closes the prior Workday blind spot (Maxar/Trimble/Sierra/NCAR now verifiable). Now
  documented in SKILL.md Phase 3a. Finding: entry-level pure-quantum-software in CO/remote
  is scarce; entry-mid fits cluster in quantum-adjacent (space/sci-computing) + general SWE/AI.

### Step 5 — Optional export (CSV + Markdown + .docx)  ☑
- ☑ `export --format csv` — flat, one row per job, all 22 columns (stdlib `csv`)
- ☑ `export --format md` — tiered Markdown report w/ excluded-wrong-location section (stdlib)
- ☑ `export --format docx` — tiered Word report, one table per tier (lazy `python-docx`
  1.2.0 present; skips gracefully w/ install hint if absent — core stays dependency-free)
- ☑ `export --format all` — writes all three; honors all `query` filters; default out dir
  `exports/<slug>_pipeline_<date>.<ext>`
- ☑ 7 export assertions added to test_jobsdb.py — **63/63 total pass**
- ☑ Query filter logic refactored into shared `job_filter_clause()` (DRY: query + export)

---

## Key design decisions (locked)

1. **Dedup key** = canonical `platform:slug:jobid` (e.g. `greenhouse:infleqtion:12345`).
   Aggregator-only roles with no ATS id fall back to `agg:<sha1(company|title|location)>`.
2. **Jobs are per-candidate** — `UNIQUE(candidate_id, dedup_key)`. Two candidates can each
   track the same posting with their own tier/fit.
3. **Upsert preserves terminal status** — a job already `applied`/`ignored`/`rejected` is
   NOT reset to `new` when it reappears in a later search; only `last_seen`/metadata refresh.
4. **Agent does fetching; CLI does storage.** `reverify list` tells the agent what to
   re-check; the agent fetches; `mark` records the outcome. No network code in the CLI.
5. **Batch JSON over many CLI calls** — the agent writes one batch file per scan into
   `job_scans/YYYY-MM-DD[_label].json` and calls `upsert-batch` once; the file is the
   dated, auditable record of that scan (kept, not deleted).
6. **Outputs:** job list = DB only; resumes & cover letters stay as `.docx`; report export
   is optional and generated from the DB in **CSV (stdlib), Markdown (stdlib), and .docx
   (lazy `python-docx`)** — `--format all` writes all three.
7. **Freshness is point-of-use, not cache-TTL.** `last_verified` is a snapshot, never a
   live guarantee; the binding check is the per-role re-verify right before applying (and
   before resume/cover work). The `reverify` window is just a sweep cost-knob: default
   `--stale-days 2`, but **Tier 1/2 are re-checked every sweep unless verified today**
   (effort concentrated on roles the candidate acts on), and `query` surfaces a `verif`
   age column so staleness is always visible. `--stale-days 0` forces a full re-check.
8. **Reporting views filter, never destroy.** `query`/`export` default to the live pipeline
   (new/active/applied) and hide `expired`/`rejected`/`ignored` so a default report never
   lists a pulled posting as a live Tier 1/2. The rows stay in the DB (history + dedup);
   `--all` (or `--status <x>`) opts back into them.

---

## Open questions / future
- Multi-candidate handoff to friends: each runs with their own resume → own categories.
- Whether to add a lightweight `view` (read-only HTML) later.
- `.docx` export needs `python-docx` (the project's only optional dependency); CSV and
  Markdown export are stdlib-only and always available.
