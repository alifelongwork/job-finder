---
name: cover-letter
description: >
  Write a cover letter for a specific job application. Use this skill whenever
  someone asks to write, draft, or create a cover letter for a role. Also
  triggers on: "write me a cover letter", "draft a letter for this job",
  "help me apply to this role", or when a job description is shared and a
  cover letter is needed. Always use this skill rather than improvising.
---

# Cover Letter Skill

## Overview

Write a cover letter that sounds like a real person wrote it, not a template,
not AI-generated boilerplate. The goal is a letter that a hiring manager reads
in full because it's direct, specific, and clearly written by someone who
understands the role and has something real to say.

---

## Phase 0: Role Verification

Roles are referenced by their `job_id` in the database. Pull the role's stored details
first (source URL, location, tier, screening risks) before writing.

Before writing the letter, confirm the role is still live. Writing a cover letter for a
pulled posting wastes effort and produces an unusable deliverable.

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

- **Confirmed still live →** proceed to Phase 1.
- **Confirmed pulled →** stop, and mark it: `python jobsdb.py mark <job_id> --status
  expired`. Tell the user the posting appears to be gone, where you checked, and offer:
  - Look for adjacent open roles at the same company
  - Skip this one
  - Manual override: if the user confirms direct access to the posting (e.g., from a
    recruiter, internal contact, or saved tab), proceed on their confirmation
- **Inconclusive →** tell the user clearly and ask them to confirm directly before
  proceeding.

### Skip condition

If the role was just verified within the same conversation (e.g., during resume tailoring
earlier in the same chat), skip Phase 0 and proceed to Phase 1.

---

## Phase 1: Input Extraction

Before writing, extract:

**From the job description:**
- What is the company actually building or doing? (not their mission statement: the real thing)
- What is the role primarily hiring for? (technical execution / leadership / TPM / hybrid)
- What are the 2–3 things they most need from this hire?
- Any specific language or requirements worth mirroring

**From the candidate's resume/profile:**
- Their single strongest credential for this specific role
- The most relevant project or program they've worked on
- Any genuine personal connection to the company's mission or technology
- Any screening risks relative to this JD

---

## Phase 2: Cover Letter Structure

Four paragraphs. Total length: 300–400 words. No filler.

### Paragraph 1: Opening hook (2–3 sentences)
- Start with something specific and genuine about the company or role
- Not "I am writing to express my interest": that is never acceptable
- Options: a specific technical aspect of what they're building, a genuine mission connection,
  something you've heard or read about the team, why this role specifically
- End with a single clear statement of why you're a strong fit

### Paragraph 2: Your strongest credential (3–4 sentences)
- Lead with the most directly relevant experience
- Be specific: project name or type, scale, what you owned, what the outcome was
- Mirror the JD's language where it's honest to do so
- Quantify where possible (team size, budget, performance spec, schedule outcome)

### Paragraph 3: Second credential or differentiator (3–4 sentences)
- Bring in your second-strongest relevant experience OR
- Address a differentiator that sets you apart from other candidates
- This is also where to briefly address a screening risk if one exists:   proactively and matter-of-factly, not apologetically

### Paragraph 4: Close (2 sentences)
- State clearly what draws you to this company specifically (not generic)
- Express interest in a conversation: no begging, no over-formality

---

## Phase 3: Tone Rules

- Write in first person, natural mid-register: professional but not stiff
- No corporate buzzwords: "synergy", "passionate", "results-driven", "proven track record"
- No excessive enthusiasm: "I am thrilled and excited" is never appropriate
- Do not restate the resume: the letter adds context the resume can't
- Contractions are fine (I've, I'm, I'd)
- One specific, genuine compliment about the company is good: flattery is not
- If there's a screening risk, address it directly and briefly: don't hide it,
  don't over-explain it

---

## Phase 4: Screening Risk Handling

If the candidate has a known gap (tool they don't use, domain they haven't worked in):

- Minor gap (preferred skill, not required): don't mention it in the cover letter
- Moderate gap (listed requirement, candidate has adjacent experience): briefly note
  the adjacent strength and move on, one sentence max
- Hard gap (true requirement candidate cannot meet): flag to the user before writing;
  if they want to apply anyway, address it directly and honestly in paragraph 3

---

## Phase 5: Output

Return the cover letter as clean text, formatted for the channel:

- Standard job application: full letter with header (name, contact, date, company, re: line)
- Portal submission (no header shown): just the body paragraphs
- Email submission: subject line + body

Write the cover letter as a `.docx` into `candidates/<slug>/cover_letters/`, then record
the path in the database:

```
python jobsdb.py mark <job_id> --cover candidates/<slug>/cover_letters/<filename>.docx
```

---

## Rules

- Always run Phase 0 role verification before writing (unless already verified in the
  same conversation)
- 300–400 words total: never longer unless the user specifically asks
- Never start with "I am writing to express my interest"
- Never list the resume in prose form: the letter is not a summary
- Never fabricate experience or claim skills the candidate doesn't have
- Never list clearance as active if it is inactive
- The letter must be specific to this company and role: a generic letter is a failure
- Filename convention: `[Company]_CoverLetter_[RoleShorthand].docx`
