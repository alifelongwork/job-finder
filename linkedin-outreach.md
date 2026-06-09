---
name: linkedin-outreach
description: >
  Find LinkedIn contacts at a target company worth reaching out to before
  applying. Use this skill whenever someone asks to find contacts, identify
  outreach targets, research who to message, or prepare LinkedIn outreach
  for a specific company or role. Also triggers on: "who should I reach out
  to at X", "find me contacts at Y", "help me with outreach before I apply".
  Always use this skill rather than improvising.
---

# LinkedIn Outreach Contact Search Skill

## Overview

Find the right people to contact at a target company before submitting an
application. The goal is to identify contacts who can either route the
application to the right person, provide a warm signal to the hiring team,
or give the candidate useful intel about the role or team.

Outreach before application is standard practice for Tier 1 roles.
Even an hour of lead time makes a difference at startups.

---

## Phase 1: Input

Before searching, confirm:
- Target company name
- Role being applied to (title, team, or JD)
- Candidate's background in one sentence (what they bring)
- Any existing connections already identified

---

## Phase 2: Contact Priority Framework

Not all contacts are equal. Prioritize in this order:

| Priority | Contact type | Why |
|----------|-------------|-----|
| ★★★ | Hiring manager for the specific role | Direct decision-maker, highest value |
| ★★★ | Person who posted the job on LinkedIn | Often HM or internal recruiter with direct line |
| ★★ | Team lead or senior engineer on the target team | Can advocate internally, provide team intel |
| ★★ | Internal recruiter at the company (not agency) | Routes applications, can flag your profile |
| ★ | Peer-level engineer on the target team | Warm introduction, can refer internally |
| ★ | Alumni connection (same school, same previous employer) | Genuine hook for cold outreach |
|, | External / agency recruiter | Lower value, they don't work at the company |
|, | C-suite / VP at large companies | Too far from hiring decision, skip |

---

## Phase 3: Search Strategy

Run these searches to find contacts. Use LinkedIn search where possible,
supplement with web search for names and roles.

### Search 1: Who posted the job
```
"[company name]" "[role title or keyword]" site:linkedin.com
"[company name]" hiring "[role keyword]" linkedin.com/posts
```

### Search 2: Team leads and senior engineers
```
"[company name]" "[team name or domain]" "lead" OR "principal" OR "staff" OR "director" site:linkedin.com
"[company name]" "[technical keyword]" engineer linkedin
```

### Search 3: Internal recruiters and talent team
```
"[company name]" "recruiter" OR "talent" OR "people" site:linkedin.com
"[company name]" "head of talent" OR "engineering recruiter" linkedin
```

### Search 4: Alumni hooks
```
"[candidate's previous employer]" "[target company]" linkedin
"[candidate's university]" "[target company]" site:linkedin.com
```

### Search 5: Direct company LinkedIn page
Check the company's LinkedIn "People" tab directly for:
- Anyone with "engineering" + "lead" or "director" in the target domain
- Anyone who has posted recently about hiring or the team

---

## Phase 4: Contact Assessment

For each contact found, assess:

- **Relevance**: How close are they to the hiring decision?
- **Hook**: Is there a genuine reason to reach out? (shared background, their public post, their specific work)
- **Reachability**: Are they active on LinkedIn? (recent posts, engagement)

Flag contacts where there is NO genuine hook, cold outreach with no hook
has low response rates and can hurt more than help.

---

## Phase 5: Output Format

Return a prioritized contact list:

### Priority Contacts

| Priority | Name | Title | Company | Hook | Recommended action |
|----------|------|-------|---------|------|--------------------|
| ★★★ | [Name if found] | [Title] | [Company] | [Why reach out] | [Message or connection request] |

If a name could not be confirmed (only a role type identified), say so clearly.
Do not invent names.

### Outreach Notes
- Which contacts to message before applying vs. after
- Any contacts to skip and why
- Suggested sequencing (who first, who second)

---

## Phase 6: Message Drafting (optional)

If the user asks for message drafts, apply these rules:

**Format:** 3–4 sentences max. No more.

**Structure:**
- Sentence 1: specific hook (their post, their work, shared background): not generic
- Sentence 2: one sentence on who you are and why it's relevant to them
- Sentence 3: what you're asking (brief call, their perspective, referral)
- Optional sentence 4: one specific credential or detail to build credibility

**Tone rules:**
- Informal, natural, mid-register: not templated, not stiff
- Do not use: "I hope this message finds you well", "I came across your profile",
  "I would love to connect", "I am reaching out because"
- Sound like a peer, not a job seeker cold-pitching
- Personalize per contact: the same message to every person is immediately obvious

**What NOT to ask for in a first message:**
- A referral (too early: build rapport first)
- A job (never)
- A long call or meeting

**What TO ask for:**
- 15–20 minutes to learn about the team
- Their perspective on the role or company
- Whether they'd be open to a quick conversation

---

## Rules

- Never invent or guess names: only report contacts that were actually found
- Always identify the hook before drafting a message: no hook, no message
- Prioritize genuine connections over volume: 2 strong contacts beat 10 weak ones
- Outreach goes before application submission for Tier 1 roles: sequence matters
- Flag if a contact appears to be an external recruiter vs. internal: different value
