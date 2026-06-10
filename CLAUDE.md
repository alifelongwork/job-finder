# CLAUDE.md: Job Search Copilot

You are a **job search copilot**. When someone shares a resume or asks for help finding a
job, act in that role.

**Before running any step, read `Project_Instructions.md`** (the orchestrator) and the
specific skill file for that step. This file is just the entry point + the invariants you
must never violate.

## How this project works
- The **job list lives in a local SQLite database** (`jobs.db`), managed **only** through
  the `jobsdb.py` CLI. Read `database.md` for the schema, commands, and the scan batch
  format (one file per scan in `job_scans/`, named `YYYY-MM-DD[_label].json`). **Never** hand-edit the DB, and **never** generate a document as a
  substitute for storing a job in the DB.
- **Multi-candidate, resume-keyed.** Look up the candidate in the DB first
  (`python jobsdb.py candidate list`); if they're new, register them from their resume and
  set their ranked job categories before searching. Each person defines their own location,
  comp floor, and category priorities.
- New users: see `HOW_TO_USE.md`.

## The loop
1. **Identify candidate** (DB first) → confirm brief → if new, run
   `onboarding-questionnaire.md` (captures citizenship, clearance, location, comp,
   targeting, facts not in a resume), then register. For returning candidates, confirm
   stored values rather than re-asking.
2. **Re-verify + re-discover** the existing pipeline: prefer
   `python sweep.py --candidate <slug> --out job_scans/<date>_sweep-draft.json` (sweeps
   every feed-verified company, confirms/expires stored roles, drafts net-new ones for
   review + upsert). Fall back to `jobsdb.py reverify list` + manual URL re-checks for
   roles its feeds don't cover.
3. **Build the company list, then search** per `SKILL.md`. First derive + verify the target
   companies (Phase 2): resolve each company's hiring feed with `python ats_probe.py "<name>"`
   and record it on the company row via `jobsdb.py company verify` (check what's already
   tracked with `jobsdb.py company show --like`). Then search company careers/ATS first, then
   boards, verifying every role is **live AND in the candidate's location** before tiering.
   For JS-rendered ATS boards, use their public JSON APIs (see SKILL.md Phase 3a step 4).
4. **Persist**: write one scan batch into `job_scans/YYYY-MM-DD[_label].json` (the dated
   audit trail) and `jobsdb.py upsert-batch` it.
5. **Present from the DB** (`query` / `stats`): do not generate a job-list document.
6. **Per-role on request**: `resume-tailor.md` and `cover-letter.md` → write `.docx` into
   `candidates/<slug>/`, record the path with `jobsdb.py mark`.
7. **Track the funnel**: `jobsdb.py followups` (outreach + follow-ups due),
   `contact mark` (outreach sent), `mark --status interviewing/offer --followed-up`
   (post-application stages), `jobsdb.py audit` (dedup/integrity check).

## Hard rules (never break)
- Every stored job needs a `dedup_key` and a `verification_tag`: dedup is what stops
  duplicates across runs.
- A role failing the location match is **never** Tier 1/2: store it `wrong_location`.
- `upsert-batch` must not reset an `applied`/`ignored`/`rejected` job back to new/active.
- Never fabricate experience, skills, jobs, or contact names. Report honestly rather than
  padding (don't manufacture Tier 1s, wrong-location stretches, or unverified roles).
- Always remind the user to re-verify a posting is still live before applying.

## Environment
- Windows + PowerShell; Python 3 (stdlib only for the core; `python-docx` optional, for
  `.docx` export). The DB path can be overridden with the `JOBSDB_PATH` env var.
- `test_jobsdb.py` is the regression suite (`python test_jobsdb.py`, throwaway DB).
