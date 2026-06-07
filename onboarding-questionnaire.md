# New Candidate Onboarding Questionnaire

Run this when registering a **new** candidate (a resume with no match in the database).
Its purpose is to capture the screening-critical facts that **drive fit assessment** but
that resumes almost never state — work authorization, clearance, location/remote, comp,
and targeting.

## How to run it

1. **Extract everything you can from the resume first.** Name, email, location of
   residence, degrees, years of experience, skills. Don't ask for what the resume already
   gives you.
2. **Then ask only the gaps below.** Onboarding is the one time it's fine to present the
   core questions as a single short list (rather than one at a time) so the candidate can
   answer in one pass. Lead with the **Required** block.
3. **For a returning candidate, don't re-ask** — show the stored values (`jobsdb.py
   candidate show --slug <slug>`) and ask them to confirm or correct.
4. **Save answers** with `jobsdb.py candidate add` (+ `category set`). Each question notes
   the DB field its answer maps to.

---

## Required (do not start a search without these)

1. **Work authorization / citizenship** → field `citizenship`
   - Are you a US citizen, permanent resident (green card), or on a visa? If a visa, which,
     and do you need sponsorship now or in the future?
   - *Why:* many defense/quantum/space roles require a "US person"; some exclude certain
     nationalities; others won't sponsor. This gates whole categories of roles.
   - *Examples to store:* `"US Citizen"`, `"Green Card (no sponsorship needed)"`,
     `"F-1 OPT, will need H-1B sponsorship in 2027"`.

2. **Security clearance** → field `clearance`
   - Do you hold an active clearance (what level + agency)? Previously held (what level,
     when did it lapse)? None, but eligible to obtain? Not eligible?
   - *Why:* cleared roles are a hard gate; "previously held, eligible for reinstatement" is
     a real asset worth recording. Never list an inactive clearance as active.
   - *Examples:* `"none"`, `"none, eligible to obtain (US citizen)"`,
     `"previously held Secret, lapsed 2024, eligible for reinstatement"`, `"active TS/SCI"`.

3. **Location & work mode** → field `location_constraint`
   - Where do you want to work — specific cities, a metro, or fully remote?
   - Remote / hybrid / onsite preference?
   - Willing to relocate? If so, where?
   - *Why:* this is the mandatory Phase 4c gate. Capture it as one rich sentence.
   - *Example:* `"Arvada, CO — Colorado-based or fully remote only, no relocation"`.

---

## Compensation

4. **Minimum acceptable comp (floor)** → field `comp_floor` (annual USD integer)
5. **Target comp** (optional) → field `comp_target` (annual USD integer)
   - *Why:* lets the search flag comp mismatches and sort. Store numbers, not ranges.

---

## Targeting

6. **Ranked job categories** → `candidate_categories` (via `category set`)
   - List the industries / role types you want, **best first**. These drive which searches
     run and in what priority order.
   - *Examples:* a SWE — 1) Quantum software/computing, 2) Quantum-adjacent software,
     3) General SWE/AI; an IT admin — 1) Systems/Infrastructure admin, 2) Cloud/DevOps ops,
     3) IT lead. (See `examples/` for full worked profiles.)

7. **Seniority you're targeting + your years of experience** → field `notes`
   - This can be a **range / multiple levels** (e.g. "new-grad through mid"), not a single
     pick — record all levels they'd accept, plus their actual YOE.
   - *Why:* prevents over/under-leveling mismatches. (We've seen early-career candidates
     screened out by Senior/Staff postings — record the real level so tiering is honest.
     Levels above the target range get surfaced but flagged as over-leveled reaches.)

8. **Companies to avoid / already applied to / on cooldown** → field `notes`

9. **Timeline urgency** → field `notes`
   - ASAP, casually looking, or targeting a specific start date?

---

## Optional context (ask once, briefly)

10. **Anything else that should shape the search?** → field `notes`
    - Industry exclusions (e.g. no gambling/defense), mission preferences, part-time vs
      full-time, contract vs FTE, visa timing, accessibility needs, etc.

---

## After the questionnaire

- Read the brief back as one block and get confirmation before searching.
- Persist: `jobsdb.py candidate add --resume <path> --slug <slug> --field citizenship=...
  --field clearance=... --field location_constraint=... --field comp_floor=... --field
  comp_target=... --field notes=...`, then `jobsdb.py category set`.
- Then proceed to the search (SKILL.md). The stored `citizenship` and `clearance` are used
  directly in Phase 5 fit assessment and screening-risk flags.
