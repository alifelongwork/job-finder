# How to Use the Job Search Copilot

A personal job-hunting assistant that finds real, verified openings, keeps them in a
local database (so nothing gets lost or duplicated between searches), and helps you
tailor resumes and cover letters for the ones you want.

You mostly just **talk to Claude**. The database and commands below are there when you
want to inspect or manage your pipeline yourself.

---

## 1. What you need (one-time)

- **Claude Code** installed (CLI, desktop, or web), opened **in this folder**. New to it? The
  [README](README.md) has step-by-step install instructions for every OS.
- **Python 3** (check with `python --version`: any 3.8+ is fine). It's already on most
  machines.
- *(Optional)* **python-docx**, only if you want Word (.docx) report exports:
  ```
  pip install python-docx
  ```
  Everything else, searching, the database, CSV and Markdown exports, works without it.

You do **not** need to know Python or SQL. Claude runs the commands for you.

---

## 2. First-time setup (2 minutes)

Open Claude Code in this folder and paste this as your first message:

> **"Read Project_Instructions.md and be my job search copilot. Here's my resume: `<path
> to your resume file>`. I'm looking for work, please set me up and run a search."**

Claude will:
1. Read your resume and pull out your name, location, and background.
2. Walk you through a short **onboarding questionnaire** for things resumes don't usually
   say but that matter a lot for matching: **work authorization / citizenship**, **security
   clearance** (none / active / previously held), **where you want to work** (cities, metro,
   or fully remote) and relocation, your **comp floor/target**, and any companies to avoid
   or timeline. (Answer what applies, e.g. "US citizen, no clearance, remote-only.")
3. Ask you to rank the **kinds of jobs you want**, in priority order: yours are whatever fits
   your field. For example, a software engineer might rank "quantum software → quantum-adjacent
   → general SWE/AI"; an IT admin might rank "systems/infrastructure → cloud/DevOps ops → IT
   lead." List the industries/role types you care about, best first.
4. Save all of that to the local database so it remembers you next time.
5. Run the search and store the results.

That's it. From then on, every new session, just say *"Read Project_Instructions.md and
be my job copilot"* and it will already know who you are.

> **Tip:** If you'd rather not retype that opening line each time, ask Claude to "create a
> CLAUDE.md that loads the job copilot instructions", Claude Code reads `CLAUDE.md`
> automatically at the start of every session.

---

## 3. The job-hunt loop

Once you're set up, the normal rhythm is:

| Step | What you say / do | What happens |
|------|-------------------|--------------|
| **Search** | "Run a search" / "find me new roles" | Claude searches company career pages and job boards, **verifies each posting is actually live and in your location**, ranks them into tiers, and saves them. |
| **Review** | "Show me my Tier 1 roles" | Claude shows your pipeline. You decide what to pursue. |
| **Outreach** | "Find me contacts at \<company\>" | Claude finds the right people to message on LinkedIn before you apply. |
| **Tailor** | "Tailor my resume for job 3" | Claude re-checks the role is still open, then writes a tailored resume `.docx`. |
| **Cover letter** | "Write a cover letter for job 3" | A specific, non-generic cover letter `.docx`. |
| **Apply** | (you apply on the company site) |, |
| **Track** | "Mark job 3 as applied" | Claude records it so it never shows up as "new" again. |

You can run a search as often as you like. **Re-running never creates duplicates**, it
updates what's there and only adds genuinely new postings. Jobs you've already applied to
stay marked as applied.

### Understanding the tiers and tags

- **🔴 Tier 1**: strong fit, apply now. **🟡 Tier 2**, good fit, worth tailoring for.
  **🟢 Tier 3**, partial fit, monitor.
- **Source tags:** `verified` = confirmed live on the company's own site in your location;
  `wrong_location` = real but in the wrong place (auto-excluded, shown separately);
  `aggregator` = seen on a job board but not yet confirmed on the company site;
  `unverified` = couldn't confirm. Always trust `verified` most.
- **Always re-check a posting is still live before you actually apply**: Claude will
  remind you. Older postings get pulled without warning.

---

## 4. Commands you can run yourself

You never *have* to run these, Claude does. But if you want to look at your pipeline
directly, open a terminal in this folder. Replace `me` with your own slug (Claude tells
you your slug; see your name with `python jobsdb.py candidate list`).

**See your jobs:**
```
python jobsdb.py query --candidate me                      # everything, ranked
python jobsdb.py query --candidate me --tier 1             # just Tier 1
python jobsdb.py query --candidate me --status new         # only ones you haven't actioned
python jobsdb.py query --candidate me --category software  # by job category
python jobsdb.py query --candidate me --status applied     # what you've applied to
```

**See a summary of your whole pipeline:**
```
python jobsdb.py stats --candidate me
```

**Mark progress on a job (use the id from `query`):**
```
python jobsdb.py mark 3 --status applied        # you applied
python jobsdb.py mark 3 --status ignored        # not interested, hide it
python jobsdb.py mark 3 --status expired        # posting is gone
python jobsdb.py mark 3 --note "recruiter emailed me"
```

**Find postings that should be re-checked for freshness:**
```
python jobsdb.py reverify list --candidate me
```

**Look up or check a company:**
```
python jobsdb.py company list                  # all companies being tracked
python jobsdb.py company show --like acme       # find one by partial name
python jobsdb.py company show "Acme Robotics"   # full record + whether its feed is verified
```
You can also just ask Claude "is \<company\> actually hiring, and what's their careers feed?"
, it resolves the company's job feed and records the result so future searches hit it directly.

**Statuses you'll see:** `new` (just found) · `active` (confirmed still live) · `applied` ·
`expired` (gone) · `rejected` · `ignored` (you hid it).

---

## 5. Exporting a report

Want a spreadsheet or a Word document of your pipeline? Ask Claude "export my pipeline,"
or run:
```
python jobsdb.py export --candidate me --format all
```
This writes four files into the `exports/` folder:
- **`.xlsx`**: an Excel workbook, one row per job, **color-coded by status** (green=active,
  red=expired, amber=new, blue=applied, orange=rejected, grey=ignored), with a frozen header
  and autofilter. No install needed, it's the spreadsheet most people want.
- **`.csv`**: the same columns as plain text (Excel / Google Sheets), sortable and filterable.
- **`.md`**: a clean tiered report you can read or paste anywhere.
- **`.docx`**: the formatted Word report (needs `python-docx`; skipped with a note if you
  don't have it).

Use `--format xlsx` (or `csv`, `md`, `docx`) for just one. Add **`--all`** to include your full
history, expired/rejected/ignored rows too (they show red/grey); without it you get just the
live pipeline. You can also export a subset, e.g. `--tier 1` or `--status new`.

---

## 6. Sharing this with more than one person

The system is built for multiple people. Two easy options:

- **Simplest: separate folders:** each person gets their own copy of this folder. On
  first use, Claude registers them from their resume. Their data lives in their own
  `jobs.db`.
- **One folder, separate databases:** set an environment variable so each person points at
  their own database file:
  ```
  # Windows PowerShell
  $env:JOBSDB_PATH = "C:\path\to\my_jobs.db"
  # Mac/Linux
  export JOBSDB_PATH=/path/to/my_jobs.db
  ```
  Then run `python jobsdb.py init` to create it. (Claude can do this for them.)

Either way, each person defines **their own** location, comp floor, and ranked job
categories, the search adapts to whoever's resume it's given.

> **Before handing off:** if you don't want a friend to see your stored jobs, give them a
> copy of the folder with the `jobs.db` file deleted (Claude will recreate it on first use),
> or have them set `JOBSDB_PATH` to a fresh file.

---

## 7. Troubleshooting

- **"Database not found. Run: python jobsdb.py init"**: the database hasn't been created
  yet. Run `python jobsdb.py init` (or just tell Claude to set you up).
- **A posting Claude found is already gone**: that's expected occasionally; re-checking is
  built in. Run a `reverify` or just tell Claude, and it'll mark dead ones expired.
- **No Tier 1 results / very few matches**: that's honest, not a bug. The tool won't pad
  your list with wrong-location or unconfirmed roles. Try broadening your categories, or
  ask Claude to include earlier-career roles.
- **Word export didn't appear**: install it with `pip install python-docx`. CSV and
  Markdown always work.
- **Weird characters in the terminal**: cosmetic only (Windows console + special symbols);
  the saved files are correct.

---

## 8. For the curious (optional)

- `PROJECT_PLAN.md`: how the whole thing was designed and built.
- `database.md`: the technical contract (schema + every command in detail).
- `SKILL.md` / `Project_Instructions.md` / `resume-tailor.md` / `cover-letter.md` /
  `linkedin-outreach.md`, the instructions Claude follows for each step.
- `test_jobsdb.py`: a self-test. Run `python test_jobsdb.py` to confirm the tool works on
  your machine (it uses a throwaway database and won't touch your data).
- `job_scans/`: a dated record of every search (one `YYYY-MM-DD.json` per scan). You don't
  need to touch these; they're the audit trail of what each search found.
- `exports/`: where `export` writes your Excel / CSV / Markdown / Word report snapshots.

Nothing here sends your data anywhere, the database is a single local file. Searching uses
the web (that's how it finds jobs), but your résumé and pipeline stay on your computer.
