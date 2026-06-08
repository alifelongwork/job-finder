# Field Notes — Colorado Quantum / Deep-Tech (worked example)

These are **real, dated findings** accumulated while running this copilot for one candidate
(an early-career SWE/ML engineer, Colorado-or-remote, quantum-first). They are kept as a
**worked example** of the kind of domain knowledge a search run accumulates — not as part of
the general method. The reusable *techniques* live in `SKILL.md` (the "ATS Cookbook" and
Phase 3a); this file is the *domain-specific residue* of applying them to one field.

When you run the copilot for a different candidate/field, you will build your own equivalent
of this file. Treat the specifics below as illustrative, and **re-verify before relying on
them** — feeds drift, companies get acquired, and careersite names change.

See also: `Elevate_Quantum_Company_Map.md` (a sample target-company map for the CO quantum
consortium).

---

## ATS feed drift / acquisitions observed (re-derive, don't assume)

- **Quantinuum** moved off US Lever → **EU Lever** (`api.eu.lever.co/v0/postings/quantinuum`).
  When `api.lever.co` 404s for a slug, try the EU instance.
- **Weights & Biases** was acquired by **CoreWeave** → roles now on the Greenhouse board token
  `coreweave` (old `lever:wandb` 404s). Reconciled with:
  `company rename --from "Weights & Biases" --to "CoreWeave" --ats-slug coreweave` then
  `company add --name "CoreWeave" --ats-platform greenhouse` (platform change needs the
  follow-up `add`, since `rename` has no `--ats-platform`).
- Several cos moved onto **Rippling** off Greenhouse/Lever (Boom Supersonic, D-Wave Quantum,
  Swimlane — verified 2026-06-04).
- **Classiq, Quantum Machines** are on **Comeet**; **Uplight, Exabeam/LogRhythm** on **Jobvite**.

## Phenom-portal / gated-Workday employers (no clean public JSON)
EchoStar, Spectrum/Charter, OpenText, NetApp, Oracle route through a Phenom branded portal
(`jobs.[company].com`) or a Workday tenant whose CXS endpoint bot-blocks (HTTP 422/403).
Verify on the branded careers page and tag the role `unverified` until re-confirmed live.

## National labs & research institutions (CO) — DO NOT assume USAJOBS
Most run their OWN career site and must be swept there:
- **National Laboratory of the Rockies (NLR)** — formerly **NREL**; DOE renamed it Dec 2025
  (new site `nlr.gov`). Careers run on the SAME Workday tenant `nrel`, but the careersite path
  is now **`/NLR`** (old `/NREL` deprecated). Verified 2026-06-03: `POST /wday/cxs/nrel/NLR/jobs`
  returns 200 with the full feed; the old `/NREL` list 404'd. dedup_key stays `workday:nrel:{reqid}`
  (tenant unchanged). **Lesson:** when a Workday list endpoint 404s, the careersite *name* is
  wrong — find the right one from the org's careers landing page, don't assume it matches the
  URL slug.
- **NCAR/UCAR** — `ucar.wd5.myworkdayjobs.com/UCAR_Careers` (Workday, list endpoint works).
  reqids use `REQ-2026-49-#`, not `R#####`.
- **Ball Aerospace → BAE Systems Space & Mission Systems** (renamed after the 2024 BAE
  acquisition; `jobs.baesystems.com`, Phenom over Kenexa BrassRing — NOT Workday; CO space
  roles, most hard-require an active clearance).
- **SwRI** — own ATS at `swri.org/careers`. **LASP** — via CU Boulder (`jobs.colorado.edu`,
  Workday/Taleo). **NIST** is the genuine federal exception → **USAJOBS.gov** (citizenship
  gate; GS series often 1550/0854).

## Re-verification caveat seen in practice
2026-06-04 sweep: Workday-absence false-flagged 2 live roles (UCAR + NLR) as gone, because
the CXS list returned a capped subset and UCAR's reqid scheme didn't match the stored
`ats_job_id`. The GET job-detail endpoint (200=live, 404=gone) was the tiebreak. (This is why
the general caveat in `SKILL.md` says: never auto-expire a Workday role on sweep-absence.)

## Google careers (embedded-data board) — quantum query result
Verified 2026-06-03 via `python google_careers.py "quantum" --state CO`: 20 live "quantum"
reqs total, only 3 in CO (all Boulder neutral-atoms **PhD Research Scientist** roles —
over-leveled for early-career; no CO-located SWE role). The Quantum AI software roles
(Decoding/QKernel/SWE III) sit in Goleta/Santa Barbara/LA — stored `wrong_location` for a
CO-only candidate.

## Landscape note (durable, not a count)
CO entry-level *quantum software* is genuinely scarce; the level-matched unclearanced lanes
are (1) big-tech CO engineering offices' new-grad programs (HPE Ft Collins, NetApp/Google/
Amazon Boulder/Denver, Oracle Broomfield) and (2) CO scientific-software shops (LASP &
CIRES/NOAA via jobs.colorado.edu — US-citizen, no clearance; SwRI Boulder; Tech-X Boulder
HPC sim). Most CO quantum/photonics consortium companies post only optics/EE/scientist/fab
roles with no early-career SWE, so they sit as `jobs=0` manual-monitors per the
completeness rule.
