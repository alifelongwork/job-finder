---
name: resume-tailor
description: >
  Tailor a resume for a specific job. Use this skill whenever someone asks to
  tailor, customize, or optimize their resume for a role or job description.
  Also triggers on: "update my resume for this job", "rewrite my resume",
  "adjust my resume", or when a job description is shared alongside a resume.
  Always use this skill rather than improvising — it produces consistent,
  high-quality tailored output.
---

# Resume Tailoring Skill

## Overview

Take a candidate's base resume and a target job description and produce a
tailored resume variant that maximizes fit without misrepresenting experience.

The goal is not to keyword-stuff. It is to surface the most relevant parts of
the candidate's real background in the right order, with the right framing,
for this specific role.

---

## Phase 0: Role Verification

Roles are referenced by their `job_id` in the database. Pull the role's stored details
first (`python jobsdb.py query --candidate <slug> --format json` and find the id, or look
it up directly), which gives you the source URL, location, tier, and screening risks.

Before tailoring anything, confirm the role is still live. Tailoring a resume for a
pulled posting wastes the candidate's time and produces a deliverable they can't use.

### Verification steps

1. **Try the source URL** from the job search report (or the URL the user provided).
   `web_fetch` the URL.
2. **If the URL is dead, 404s, or shows "this position is no longer open":** try the
   company's careers page directly (`[company].com/careers` or equivalent).
3. **If the company page is JS-blocked or inaccessible:** check the company's ATS
   subdomain (`boards.greenhouse.io/[company]`, `jobs.lever.co/[company]`,
   `jobs.ashbyhq.com/[company]`, `apply.workable.com/[company]`,
   `jobs.smartrecruiters.com/[company]`).

### Outcomes

- **Confirmed still live →** proceed to Phase 1. Note the verification in the
  tailoring summary and refresh the DB: `python jobsdb.py mark <job_id> --verified`.
- **Confirmed pulled (clear 404 or "no longer open" message) →** stop, and mark it in the
  DB: `python jobsdb.py mark <job_id> --status expired`. Tell the user the posting appears
  to be gone, where you checked, and offer options:
  - Look for adjacent open roles at the same company
  - Skip this one
  - Manual override: if the user has direct access to the posting (e.g., from a
    recruiter, internal contact, or a tab they have open) and confirms it's still
    live, proceed with tailoring on their confirmation
- **Inconclusive (company page inaccessible, no clear "pulled" signal) →** tell the
  user clearly: *"I couldn't confirm the posting is still live — the career page is
  blocked. Can you check directly and confirm before I tailor?"* Wait for their
  confirmation before proceeding.

### Skip condition

If the role was just verified within the same conversation (e.g., during cover letter
writing earlier in the same chat), skip Phase 0 and proceed to Phase 1.

---

## Phase 1: Input Extraction

Before tailoring, extract:

**From the job description:**
- Role title and level (Senior / Staff / Principal / Lead)
- Top 3–5 required skills or experiences
- Top 2–3 preferred / bonus skills
- Hard requirements (tools, clearances, degrees)
- Role framing: is this primarily technical execution, leadership, or hybrid?
- Any screening risks for this candidate (tools they lack, domain gaps)

**From the base resume:**
- Candidate's strongest matching experiences (rank by relevance to JD)
- Existing professional summary
- Technical skills section
- Any bullet points that directly match JD language or requirements

---

## Phase 2: Tailoring Strategy

Decide the framing before writing anything.

Ask: what is this role primarily hiring for?

| Role type | Lead with |
|-----------|-----------|
| Technical execution (hands-on engineer) | Hands-on technical depth, specific systems, lab/test experience |
| Technical leadership (staff/principal) | System architecture, cross-functional ownership, program outcomes |
| TPM / program delivery | Schedule, budget, subcontractor execution, hardware delivery |
| Hybrid | Lead with technical depth, support with execution proof points |

Then identify:
- Which 2–3 bullet points from the base resume are the strongest matches — move these to the top of the most recent role
- Whether the professional summary needs to be rewritten for this framing
- Whether the skills section ordering needs to shift (put most-relevant domain first)
- Any screening risks to address (see rules below)

---

## Phase 3: Tailoring Execution

### Professional Summary
- Rewrite to match the role framing (technical / TPM / hybrid)
- 3 sentences, ~65–70 words maximum
- Sentence 1: what you are + your strongest credential for this role
- Sentence 2: your most relevant project or program outcome
- Sentence 3: what you bring that others don't (differentiator)
- Do not use generic phrases like "proven track record" or "results-driven"

### Experience Bullets
- Reorder bullets within each role so the most JD-relevant ones appear first
- Rewrite up to 3 bullets per role to more directly mirror JD language — without fabricating
- Do not add experience the candidate does not have
- Quantify wherever possible (team size, budget, schedule outcome, performance spec)
- Remove or compress bullets that are irrelevant to this specific role

### Skills Section
- Reorder skill categories so the most relevant domain appears first
- Add any legitimate skills from the JD that the candidate has but hasn't listed
- Do not add skills the candidate cannot honestly claim

### Title / Header
- Adjust the tagline under the candidate's name to match the role title
  (e.g. "Optical Payload Lead | EO/IR Systems Engineer" → "Systems Engineer | Space Imaging | EO/IR Payloads")

---

## Phase 4: Screening Risk Handling

If the candidate has a known gap relative to the JD (a required tool they don't use,
a domain they haven't worked in directly), apply this rule:

**Do not self-select out — but do not hide the gap either.**

- If the gap is a preferred/bonus skill: ignore it, don't mention it in the resume
- If the gap is a listed requirement but not truly hard: frame adjacent experience as
  close as possible; flag in cover letter if needed
- If the gap is a hard requirement the candidate genuinely cannot meet: flag it clearly
  to the user and let them decide whether to apply

Never add a skill to the resume that the candidate does not actually have.

---

## Phase 5: Output Format

Return:

### Tailoring Summary
- Role verification status (confirmed live / user-confirmed manually / inconclusive)
- Role framing chosen and why
- Top 3 changes made
- Any screening risks identified and how they were handled

---

### Tailored Resume (full text)

Return the complete tailored resume text, formatted consistently with the base resume.

Write the tailored resume as a `.docx` into `candidates/<slug>/resumes/` using the Write
tool (or a docx helper), then record the path in the database:

```
python jobsdb.py mark <job_id> --resume candidates/<slug>/resumes/<filename>.docx
```

---

## Rules

- Always run Phase 0 role verification before tailoring (unless already verified in the
  same conversation)
- Keep the professional summary to 3 sentences / ~65–70 words
- Never fabricate experience, skills, or outcomes
- Never list a clearance as active if it is inactive — always use "previously held, eligible for reinstatement"
- Technical precision matters — do not change specific performance specs (wavelengths, tolerances, budget figures) unless correcting a known error
- The resume should read as the candidate's voice, not as a rewrite
- Filename convention: `[CandidateName]_Resume_[Company]_[RoleShorthand].docx`
