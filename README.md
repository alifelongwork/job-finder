# Job Search Copilot

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-FF5E5B)](https://ko-fi.com/alifelongwork)


A personal, **resume-keyed** job-hunting copilot you run inside [Claude Code](https://claude.com/claude-code).
It finds **real, verified, location-matched** job openings, keeps them in a local SQLite
database (so nothing is lost or duplicated between searches), and tailors resumes and cover
letters for the ones you want. It works for **any field** such as software, IT/sysadmin, healthcare,
finance, trades because the search adapts to whoever's resume it's given. This is meant to drastically simplify the job searching process.

> **This is a template.** Use it to create your own copy (see Setup below), open the folder
> in Claude Code, and point it at your resume. Your data (`jobs.db`, your resume, generated
> docs) stays local and is gitignored so nothing personal is committed or sent anywhere.

## What it does

```
upload resume → store candidate brief → find companies that hire your profile
   → verify each company's hiring feed → search open roles (verified live + in your location)
   → store & tier results → tailor resume / cover letter on request
```

Three principles drive quality: **start from companies, not job boards**; **the company's own
careers page/ATS is the only authoritative source**; and **a live posting in the wrong
location is not a match** (location is a hard gate, never a Tier 1/2).

## Do I need Claude Code? (what's automated vs. what runs standalone)

The **searching and judgment** are the product, and those need an LLM agent where **Claude Code is
the intended driver.** The database and helper scripts, however, are plain Python and run on
their own:

| Part | Needs Claude Code? | Notes |
|------|--------------------|-------|
| Discovering companies for your profile, multi-source search, deciding fit / location / tier, writing tailored resumes & cover letters | **Yes** | This is the agent's work. The `*.md` files are instructions *for the LLM*, not runnable code. |
| `jobsdb.py` - store / query / dedup / export your pipeline, `company verify`, stats, audit, follow-up tracking | **No** | Pure Python 3 (stdlib `sqlite3`), **zero network**. Works fully offline. |
| `sweep.py` - re-scan every verified company feed: confirm/expire stored roles, draft net-new ones, backfill salary ranges | **No** | Stdlib `urllib`, no keys. The fast path for keeping the pipeline fresh. |
| `ats_probe.py` - resolve a company's ATS feed & list its open roles (9 platforms) | **No** | Stdlib `urllib`, **no API keys**. Real web fetch without Claude. |
| `google_careers.py` / `amazon_jobs.py` / `simplify_jobs.py` - big-tech boards + the SimplifyJobs new-grad list | **No** | Stdlib `urllib`, no keys. |
| `usajobs.py` - federal roles (NIST, NOAA, ...) via the official USAJOBS API | **No** | Stdlib `urllib`; needs a **free** USAJOBS API key (the script explains the 2-minute signup). |

So: **Claude Code does the open-ended *searching* and the *reasoning*; the CLI/helpers do the
deterministic fetching and all the data management.** A person could run the CLI and helper
scripts by hand (and even drive the whole thing with a different agentic-LLM tool that has a
shell + web access, nothing here is Claude-Code-proprietary), but the turnkey experience
assumes Claude Code. There are **no API keys anywhere**, the ATS feeds and Google careers are
public endpoints.

---

## Setup - step by step

### Step 1 - Get your own copy of this project

- **On GitHub (recommended):** click **`Use this template` → Create a new repository**, then
  clone it:
  ```bash
  git clone https://github.com/<your-username>/<your-repo>.git
  cd <your-repo>
  ```
  *(If the owner hasn't enabled the template button, use **Code → Download ZIP**, or
  `git clone` the repo directly, then `cd` into it.)*
- Everything personal stays out of git automatically (`.gitignore` excludes `jobs.db`, your
  resume, `candidates/`, `exports/`, `job_scans/`).

### Step 2 - Install Python 3 (3.8 or newer)

Check whether you already have it:
```bash
python --version        # or:  python3 --version
```
If not, install from **https://www.python.org/downloads/** (or your OS package manager). No
third-party packages are required for the core; it's standard library only. *(Optional:
`pip install python-docx` only if you want Microsoft Word `.docx` report exports; CSV, Markdown,
and Excel `.xlsx` exports work without it.)*

### Step 3 - Install Claude Code

> **Account note:** Claude Code requires a paid Claude plan (**Pro, Max, Team, or Enterprise**)
> or an **Anthropic Console (API) account**, the free Claude.ai tier does not include it. (It
> can also run via AWS Bedrock / Google Vertex AI / Microsoft Foundry.)

Install with the official one-line installer for your OS:

- **macOS / Linux / WSL:**
  ```bash
  curl -fsSL https://claude.ai/install.sh | bash
  ```
- **Windows (PowerShell):**
  ```powershell
  irm https://claude.ai/install.ps1 | iex
  ```
- **Any platform, via npm** (needs **Node.js 18+**):
  ```bash
  npm install -g @anthropic-ai/claude-code
  ```
- **Homebrew (macOS/Linux):** `brew install --cask claude-code` · **WinGet (Windows):**
  `winget install Anthropic.ClaudeCode`

*(On Windows, installing **Git for Windows** is optional but recommended as it lets Claude Code
use Bash; otherwise it uses PowerShell.)*

**Prefer not to use the terminal?** Claude Code also ships as a **desktop app** (macOS/Windows,
browse to your folder in the UI) and a **web app** at **https://claude.ai/code**. The desktop
app and IDE extensions (VS Code, JetBrains) can open this local folder; the CLI below is the
simplest path.

Official docs: **install/setup** https://code.claude.com/docs/en/setup · **quickstart**
https://code.claude.com/docs/en/quickstart

### Step 4 - Start Claude Code in this folder

From the project folder you cloned in Step 1:
```bash
cd <your-repo>
claude
```
The first run opens a browser to log in to your Claude account. Running `claude` **inside this
folder** is what lets it read the copilot's instructions (`CLAUDE.md` loads automatically).

### Step 5 - Kick off your search

Paste this as your first message (point it at your résumé file either PDF or `.docx`):

> **"Read Project_Instructions.md and be my job search copilot. Here's my resume:
> `path/to/your_resume.pdf`. Please set me up and run a search."**

Claude will then:
1. Read your résumé and pull out your background.
2. Ask a few onboarding questions resumes don't answer (work authorization, location/remote,
   comp floor, target roles).
3. Save your profile to the local database.
4. Build + verify a target-company list, search their live postings, and store the tiered
   results.

### From then on

Each new session, just open the folder and run `claude`, then say *"Read Project_Instructions.md
and be my job copilot"*, it already remembers you from the database. See
**[HOW_TO_USE.md](HOW_TO_USE.md)** for the day-to-day loop (reviewing roles, tailoring a resume,
marking what you applied to), and **[examples/](examples/)** for two worked candidate profiles
(an early-career software engineer and an experienced IT/sysadmin).

---

## One database per person

Each person runs **their own** `jobs.db`. Two ways to share this with friends:

- **Separate folders** so each person gets their own copy of the template; their data lives in
  their own `jobs.db`.
- **One folder, separate DBs** and point each person at their own file:
  ```
  # Windows PowerShell
  $env:JOBSDB_PATH = "C:\path\to\my_jobs.db"
  # macOS / Linux
  export JOBSDB_PATH=/path/to/my_jobs.db
  ```
  then `python jobsdb.py init`. (Claude can do this for them.)

## Using the tools by hand (no Claude required)

These run anytime with just Python making it useful for inspecting your pipeline or checking a company:
```bash
python jobsdb.py stats --candidate <you>            # pipeline summary + category yield + comp coverage
python jobsdb.py query --candidate <you> --tier 1   # your Tier-1 roles
python jobsdb.py followups --candidate <you>        # outreach + follow-ups due
python jobsdb.py audit --candidate <you>            # duplicate / rule-violation check
python jobsdb.py company show --like acme           # is a company tracked?
python sweep.py --candidate <you>                   # re-scan every verified company feed
python ats_probe.py "Acme Robotics"                 # find a company's live ATS feed
python simplify_jobs.py "software" --state CO       # new-grad roles (SimplifyJobs list)
python test_jobsdb.py                               # self-test (throwaway DB)
```
See **[database.md](database.md)** for the full CLI.

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
| `jobsdb.py` | The pipeline CLI (stdlib only), single source of truth for the job list |
| `sweep.py` | Automated feed sweep: re-verify stored roles + draft net-new ones across all verified companies |
| `discover.py` | Location-driven company discovery: bootstraps the company list for a fresh candidate by harvesting location-scoped sources, then confirms each feed (the discovery half `sweep.py` doesn't do) |
| `companies_seed/` | Checked-in, reset-proof company baseline by region and sector (so a DB rebuild re-inherits the curated universe) |
| `ats_probe.py` | Resolves a company's ATS hiring feed across 9 platforms (company-level verification helper) |
| `google_careers.py` / `amazon_jobs.py` | Big-tech boards with no standard ATS |
| `simplify_jobs.py` | New-grad/early-career discovery (SimplifyJobs list, direct ATS links) |
| `usajobs.py` | Federal roles via the official USAJOBS API (free key) |
| `test_jobsdb.py` | Regression suite (`python test_jobsdb.py`, throwaway DB) |
| `examples/` | Worked candidate profiles + a sample company map |

## Changelog

Major additions are logged here, newest first. Routine fixes and doc tweaks live in the git
history; this section calls out the features worth knowing about.

### 2026-06-25 - company discovery + EU-Lever sweep fix

**Added**
- **Location-driven company discovery (`discover.py`).** Bootstraps the company database for a
  fresh candidate from their location plus ranked categories: it harvests location-scoped
  sources (the SimplifyJobs list, USAJOBS for citizens, best-effort Built In, and an
  accumulating `companies_seed/` library), extracts each employer and any ATS apply link,
  confirms the hiring feed via `ats_probe`, and writes a reviewable company batch. This is the
  discovery half that `sweep.py` does not do (the sweep only re-checks companies already
  tracked). A name-guessed feed is recorded only as a flagged lead, never trusted blindly, to
  avoid attaching the wrong company's board.
- **`jobsdb.py company verify-batch`.** Idempotent bulk company registration from a discovery
  batch: it never downgrades a stronger verification status and never overwrites a company's
  identity. Adds `region` and `discovery_source` columns to the companies table.
- **`companies_seed/` baseline.** A checked-in, reset-proof library of target companies by
  region and sector, so rebuilding the database re-inherits the curated company universe
  instead of losing it.

**Fixed**
- **EU-Lever feeds are no longer skipped by the sweep.** Store EU-based Lever companies (such
  as Quantinuum) with platform `lever` rather than `lever-eu`; the Lever fetcher already probes
  the EU host, and the old `lever-eu` value made `sweep.py` silently skip the entire feed.

## Notes

- **Nothing here phones home.** The database is one local file. The *agent* uses the web to
  find and verify jobs (that's the searching), and the helper scripts fetch public ATS feeds,
  but your résumé and pipeline stay on your machine. `.gitignore` keeps `jobs.db`, resumes,
  generated docs, and scan/export folders out of git.
- **For repo owners:** turn on *Settings → Template repository* on GitHub so others can click
  *Use this template* instead of cloning.
