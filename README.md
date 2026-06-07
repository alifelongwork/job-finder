# Job Search Copilot

A personal, **resume-keyed** job-hunting copilot you run inside [Claude Code](https://claude.com/claude-code).
It finds **real, verified, location-matched** job openings, keeps them in a local SQLite
database (so nothing is lost or duplicated between searches), and tailors resumes and cover
letters for the ones you want. It works for **any field** — software, IT/sysadmin, healthcare,
finance, trades — because the search adapts to whoever's resume it's given.

> **This is a template.** Clone it (or click *Use this template* on GitHub), open the folder
> in Claude Code, and point it at your resume. Your data (`jobs.db`, your resume, generated
> docs) stays local and is gitignored — nothing personal is committed or sent anywhere.

## What it does

```
upload resume → store candidate brief → find companies that hire your profile
   → verify each company's hiring feed → search open roles (verified live + in your location)
   → store & tier results → tailor resume / cover letter on request
```

Three principles drive quality: **start from companies, not job boards**; **the company's own
careers page/ATS is the only authoritative source**; and **a live posting in the wrong
location is not a match** (location is a hard gate, never a Tier 1/2).

## Quick start

1. Install **Claude Code** and **Python 3** (3.8+; standard library only — no pip installs
   required for the core. `python-docx` is optional, only for Word exports).
2. Open this folder in Claude Code and say:
   > *"Read Project_Instructions.md and be my job search copilot. Here's my resume: `<path>`.
   > Please set me up and run a search."*
3. Claude reads your resume, runs a short onboarding questionnaire (work authorization,
   location, comp, target categories — the things resumes don't say), saves your brief to the
   DB, builds + verifies a target-company list, searches, and stores the results.

See **[HOW_TO_USE.md](HOW_TO_USE.md)** for the full guide, and **[examples/](examples/)** for
two worked candidate profiles (an early-career SWE and an experienced IT/sysadmin).

## One database per person

Each person runs **their own** `jobs.db`. Two ways to share this with friends:

- **Separate folders** — each person gets their own copy of the template; their data lives in
  their own `jobs.db`.
- **One folder, separate DBs** — point each person at their own file:
  ```
  # Windows PowerShell
  $env:JOBSDB_PATH = "C:\path\to\my_jobs.db"
  # macOS / Linux
  export JOBSDB_PATH=/path/to/my_jobs.db
  ```
  then `python jobsdb.py init`. (Claude can do this for them.)

## What's in here

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Entry point + invariants Claude loads automatically |
| `Project_Instructions.md` | The orchestrator playbook (the loop) |
| `SKILL.md` | The search method: company-first discovery, ATS verification, location gate, tiering |
| `onboarding-questionnaire.md` | Screening facts a resume doesn't state |
| `resume-tailor.md` / `cover-letter.md` | Per-role document generation |
| `domain-boards.md` | Job-board library across many fields (IT, healthcare, finance, SWE, …) |
| `linkedin-outreach.md` | Contact search for Tier 1 roles |
| `database.md` | The DB schema + `jobsdb.py` CLI contract |
| `jobsdb.py` | The pipeline CLI (stdlib only) — single source of truth for the job list |
| `ats_probe.py` | Resolves a company's ATS hiring feed (company-level verification helper) |
| `google_careers.py` | Reads Google's embedded-data careers board |
| `test_jobsdb.py` | Regression suite (`python test_jobsdb.py`, throwaway DB) |
| `examples/` | Worked candidate profiles + a sample company map |

## Notes

- **Nothing here phones home.** The database is one local file; searching uses the web (that's
  how it finds jobs), but your résumé and pipeline stay on your machine. `.gitignore` keeps
  `jobs.db`, resumes, generated docs, and scan/export folders out of git.
- **Tip:** on GitHub, turn on *Settings → Template repository* so others can click *Use this
  template* instead of cloning.
