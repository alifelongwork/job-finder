# Domain-Specific Job Boards

Reference this file during Phase 3e to select the right boards for the candidate's domain.

> **Note on hierarchy:** These boards are **fallbacks**, not primary sources. The job
> search workflow always checks the company's own careers page (or ATS subdomain) first
> — see Phase 3a in SKILL.md. Roles discovered on the boards below are aggregator
> findings and require verification against the company's surface in Phase 4 before being
> reported as Tier 1 or Tier 2.

---

## Space / Aerospace / Defense

- **SpaceJobs.com** — space industry specific, good for payload, systems, EO roles
- **SpaceCareers.uk** — covers US roles despite the name
- **AIAA Career Center** — aiaa.org/career-center — aerospace engineering focused
- **ClearanceJobs.com** — cleared roles, excellent for defense-tech and national security space
- **DefenseJobsBoard.com** — defense contractor roles
- **LinkedIn Aerospace & Defense group job postings**

Search patterns:
```
site:spacejobs.com "[role keyword]"
site:clearancejobs.com "[role keyword]" "[location]"
"aerospace" OR "space" "[role title]" "[city]" jobs 2026
```

---

## Deep Tech / Startups / VC-Backed

- **Wellfound (formerly AngelList Talent)** — wellfound.com/jobs — best for Series A–C startups
- **YC Work at a Startup** — workatastartup.com — Y Combinator portfolio companies
- **Lux Capital portfolio jobs** — luxcapital.com/portfolio (check each company directly)
- **a16z portfolio jobs** — a16z.com/portfolio
- **Initialized Capital portfolio** — initialized.com/portfolio

Search patterns:
```
site:wellfound.com "[role title]" "[city]"
site:workatastartup.com "[domain keyword]"
```

---

## Photonics / Optics / Laser

- **SPIE Career Center** — spie.org/career-center — best specialized board for optical engineers
- **OSA/Optica Career Center** — optica.org/en-us/career_center
- **Photonics Media Job Board** — photonics.com/jobs

Search patterns:
```
site:spie.org/career-center "[role keyword]"
"photonics" OR "optical engineer" "[city]" jobs site:spie.org
```

---

## Quantum Computing / Quantum Tech

- **The Quantum Insider job board** — thequantuminsider.com/jobs
- **Quantiki job listings** — quantiki.org/positions
- **LinkedIn Quantum Computing group**

---

## Defense / Government Contractor

- **USAJobs** — usajobs.gov — federal civilian roles, labs (NIST, NRL, AFRL)
- **ClearanceJobs.com** — top source for cleared roles
- **Dice.com** — strong for defense/government contractor tech roles
- **Booz Allen, SAIC, Leidos, MITRE career pages** — hit directly, not just aggregators

---

## Robotics / Autonomous Systems

- **Robotics Jobs Board** — roboticsjobsboard.com
- **Wellfound robotics filter**
- **IEEE Spectrum job board** — jobs.ieee.org

---

## Energy / Clean Tech / Fusion

- **Climatebase** — climatebase.org — clean energy and climate tech
- **Climate Draft** — climatedraft.org
- **Fusion Industry Association member companies** — fusionindustryassociation.org/about-fusion-industry/member-companies (check each directly)

---

## Regional / Local Tech Boards

Best when the candidate is location-constrained to a specific metro. Built In runs
city-specific editions (Colorado, Austin, NYC, Chicago, LA, Seattle, Boston, etc.) — pick
the edition that matches the candidate's location.

- **Built In Colorado** — builtincolorado.com — strong for Denver/Boulder/Westminster tech,
  startups, and remote-in-CO roles. Filterable by category (dev/engineering, data/analytics,
  machine learning, AI) and by remote/entry-level.
  - Other editions: builtin.com (national), builtinaustin.com, builtinnyc.com, etc.

Search patterns:
```
site:builtincolorado.com "[role title]"
site:builtincolorado.com machine learning OR software engineer remote
"[company]" site:builtincolorado.com          # find a company's Built In profile + listings
```

**Hierarchy note:** Built In is an aggregator — it lists roles but the apply link usually
routes to the company's own ATS (Greenhouse/Lever/etc.). Treat Built In as *discovery*:
once it surfaces a company/role, verify it live on the company surface per Phase 3a/4
(prefer the ATS JSON API), and pull the location from the ATS, not Built In's label.

---

## General High-Signal Sources (use for any domain)

- **Greenhouse** — site:greenhouse.io
- **Lever** — site:lever.co
- **Ashby** — site:jobs.ashbyhq.com
- **Workable** — site:apply.workable.com
- **Jobvite** — site:jobvite.com
- **SmartRecruiters** — site:jobs.smartrecruiters.com
- **BambooHR** — site:bamboohr.com/jobs (common at smaller companies)

These are ATS platforms — search them directly with domain keywords to find roles that don't appear on LinkedIn or Indeed. **Note:** when a company is on the Phase 2 target list, prefer hitting their specific ATS subdomain directly (`boards.greenhouse.io/[company]`, etc.) per Phase 3a — that counts as company-page verification.
