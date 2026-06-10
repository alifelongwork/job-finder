# Domain-Specific Job Boards

Reference this file during Phase 3e to select the right boards for the **candidate's** domain.
It is a library across many fields, use the section(s) that match the candidate's ranked
categories, and ignore the rest. New domains can be added as you encounter them.

> **Note on hierarchy:** These boards are **fallbacks**, not primary sources. The job
> search workflow always checks the company's own careers page (or ATS subdomain) first
>, see Phase 3a in SKILL.md. Roles discovered on the boards below are aggregator
> findings and require verification against the company's surface in Phase 4 before being
> reported as Tier 1 or Tier 2.

> **How to find boards for ANY niche (when no section below fits):** search
> `"[domain] jobs" board`, `site:[professional-association].org careers`, and
> `"[role title]" "[city]" jobs`; check the professional/industry association for the field
> (most run a career center), the relevant subreddit/Slack/Discord "who's hiring" threads,
> and the portfolio pages of VCs/PE firms that invest in that vertical. Then add the good
> ones here.

---

## IT / Systems Administration / Infrastructure / Helpdesk

The IT job market is heavily **non-tech-company internal IT** (hospitals, universities,
government, finance, manufacturing) plus **MSPs** (managed service providers). Many of these
employers run iCIMS, SuccessFactors, Oracle Cloud, or Workday rather than Greenhouse/Lever, so expect the ATS Cookbook's Workday CXS path and branded-careers-page verification more than
the lightweight GET feeds.

- **Dice.com**: dice.com, the strongest general board for IT/infrastructure/sysadmin/devops
- **ClearanceJobs.com**: clearancejobs.com, cleared IT/sysadmin roles (defense/gov contractors)
- **USAJobs**: usajobs.gov, federal IT (GS-2210 series); citizenship gate
- **Built In** (city editions): strong for IT/devops/SRE at tech-forward employers
- **LinkedIn Jobs**: filter by "Information Technology" + "Administrative" function
- **r/sysadmin** & **r/ITCareerQuestions** monthly hiring threads; **MSP-focused** subreddits
- **CompTIA / association boards**; **SpiceWorks** community job posts (SMB IT)
- **Indeed / ZipRecruiter**: high volume for helpdesk/desktop-support/NOC (aggregator, verify)

Employer types to target directly (Phase 2): **MSPs / managed-IT** (Channel Futures MSP 501,
CRN MSP lists), **healthcare & hospital systems**, **universities & K-12 districts**,
**financial-services & insurance IT**, **state/local government**, **datacenter / colocation /
cloud operators**, and the **internal IT of any large local employer**.

Search patterns:
```
site:dice.com "system administrator" "[city]"
"systems administrator" OR "IT administrator" "[city]" jobs
"MSP" OR "managed services" "[city]" hiring "system administrator"
site:clearancejobs.com "systems administrator" "[location]"
"[hospital/university/city government]" careers "IT" OR "systems"
```

---

## Software Engineering / Data / ML / AI

- **Greenhouse / Lever / Ashby** ATS sweeps (see General High-Signal Sources below)
- **Built In** (city editions): dev/engineering, data, ML/AI, filterable by remote/level
- **Wellfound** (formerly AngelList): startups; **YC Work at a Startup**, workatastartup.com
- **Hacker News "Who is hiring?"** monthly thread: news.ycombinator.com (search by `[city]`/remote)
- **Otta**, **LinkedIn Jobs**; for ML/AI specifically: lab/research-org career pages
- Remote-first: **We Work Remotely**, **RemoteOK**, **Remotive**

Search patterns:
```
site:greenhouse.io "software engineer" "[location]"
site:wellfound.com "[role title]" "[city]"
"machine learning engineer" OR "ML engineer" "[city OR remote]" jobs
```

---

## New Grad / Early Career (stage-specific, any domain)

These sources are keyed to career STAGE rather than domain: for a new-grad or
early-career candidate they out-signal every domain board above, because large-company
new-grad reqs are batch-posted and vanish fast.

- **SimplifyJobs New-Grad-Positions** (GitHub): the single best new-grad SWE list,
  community-updated continuously, each listing links directly to the company ATS posting,
  dead roles are flagged. **Helper: `python simplify_jobs.py "[keyword]" --state <ST>
  [--days N]`** pulls the machine-readable list and filters by state + US-remote (with
  the foreign-remote guard). Aggregator discovery: verify each kept role on its ATS URL
  per Phase 4 before tiering.
- **SimplifyJobs Summer20XX-Internships** (GitHub): same repo family, for internships.
- **Handshake**: university-gated; employers target schools directly, so competition per
  posting is far lower than public boards. The candidate logs in with their school account
  (can't be swept from here, remind them to check it).
- **RippleMatch**: ripplematch.com, new-grad/early-career matching; candidate-side signup.
- **Untapped**: untapped.io, early-career + diversity-focused postings.
- **Company "university recruiting" / "early careers" program pages**: large employers
  post new-grad cohorts under a separate program page (e.g. `careers.[company].com/students`
  or "University Recruiting" job families) that generic title searches miss.

Sweep keyword pass (works on any ATS feed or aggregator):
```
"new grad" OR "new graduate" OR "university grad" "[year]" "[domain]"
"early career" OR "entry level" "software engineer" "[city OR remote]"
site:job-boards.greenhouse.io "new grad" "[year]"
```

---

## Healthcare / Health-IT / Clinical

- **Health eCareers**: healthecareers.com; **HealthcareSource**; **Nurse.com** (nursing)
- Hospital-system career pages directly (most on Workday/iCIMS/SuccessFactors)
- **USAJobs** (VA, IHS); **Indeed** (high volume: verify on the system's own surface)
- For health-IT/EHR (Epic/Cerner): the vendor + large provider career pages

Search patterns:
```
"[hospital system]" careers "[role]"
"registered nurse" OR "RN" "[city]" jobs
"Epic analyst" OR "EHR" "[city]" jobs
```

---

## Finance / Fintech / Insurance

- **eFinancialCareers**: efinancialcareers.com; **Built In** (fintech tag)
- Bank / insurer career pages directly (Workday/Oracle-heavy); **LinkedIn Jobs** (Finance fn)
- Fintech startups: **Wellfound**, VC portfolio pages (a16z, Ribbit, QED)

Search patterns:
```
site:efinancialcareers.com "[role]" "[city]"
"[bank/insurer]" careers "[role]"
```

---

## Marketing / Sales / Customer Success / Operations

- **LinkedIn Jobs** (Marketing/Sales functions): the primary surface for these
- **Built In**, **Wellfound** (startup GTM roles)
- **RevGenius / Pavilion** communities (sales/CS hiring channels)
- Industry-specific: **MediaBistro** (media/marketing), **Sales Talent Agency** listings

---

## Design / UX / Product

- **Dribbble Jobs**, **Behance**; **Built In** (design/product tags)
- **Designer News**, **ADPList** community boards; **LinkedIn Jobs** (Design/Product fns)

---

## Biotech / Pharma / Life Sciences

- **BioSpace**: biospace.com; **Science Careers**, jobs.sciencecareers.org
- **Nature Careers**: nature.com/naturecareers; company + CRO career pages directly

---

## Education / Academia

- **HigherEdJobs**: higheredjobs.com; **Chronicle of Higher Education** jobs
- **SchoolSpring** / district sites (K-12); university HR career pages (Workday/Taleo/jobs.[uni].edu)

---

## Skilled Trades / Manufacturing / Field Ops

- **Indeed**, **ZipRecruiter** (high volume); employer career pages
- Union hall / apprenticeship boards; **Manufacturing.net** job listings

---

## Space / Aerospace / Defense

- **SpaceJobs.com**: space industry specific (payload, systems, EO roles)
- **SpaceCareers.uk**: covers US roles despite the name
- **AIAA Career Center**: aiaa.org/career-center, aerospace engineering focused
- **ClearanceJobs.com**: cleared roles; **DefenseJobsBoard.com**, defense contractor roles
- **Booz Allen, SAIC, Leidos, MITRE** career pages: hit directly, not just aggregators

Search patterns:
```
site:spacejobs.com "[role keyword]"
site:clearancejobs.com "[role keyword]" "[location]"
```

---

## Deep Tech / Startups / VC-Backed

- **Wellfound**: wellfound.com/jobs, best for Series A–C startups
- **YC Work at a Startup**: workatastartup.com, Y Combinator portfolio companies
- VC portfolio jobs: **a16z**, **Lux Capital**, **Initialized**, **Founders Fund** portfolios
  (check each company directly)

---

## Photonics / Optics / Laser

- **SPIE Career Center**: spie.org/career-center; **Optica (OSA) Career Center**, optica.org
- **Photonics Media Job Board**: photonics.com/jobs

---

## Quantum Computing / Quantum Tech

- **The Quantum Insider job board**: thequantuminsider.com/jobs
- **Quantiki job listings**: quantiki.org/positions; **LinkedIn Quantum Computing** group
- (Worked CO-quantum target map: `examples/Elevate_Quantum_Company_Map.md`.)

---

## Robotics / Autonomous Systems

- **Robotics Jobs Board**: roboticsjobsboard.com; **IEEE Spectrum**, jobs.ieee.org
- **Wellfound** robotics filter

---

## Energy / Clean Tech / Fusion

- **Climatebase**: climatebase.org; **Climate Draft**, climatedraft.org
- **Fusion Industry Association** member companies: check each directly

---

## Government / Public Sector

- **USAJobs**: usajobs.gov (federal civilian; citizenship gate, GS series)
- **GovernmentJobs.com / NeoGov**: state & local; individual city/county/state career portals
- **ClearanceJobs.com**: cleared contractor roles

---

## Regional / Local Tech Boards

Best when the candidate is location-constrained to a specific metro. **Built In** runs
city-specific editions (Colorado, Austin, NYC, Chicago, LA, Seattle, Boston, etc.), pick the
edition that matches the candidate's location.

- **Built In**: builtin.com (national), builtincolorado.com, builtinaustin.com, builtinnyc.com,
  etc. Filterable by category and by remote/entry-level.

**Hierarchy note:** Built In is an aggregator, the apply link usually routes to the company's
own ATS (Greenhouse/Lever/etc.). Treat it as *discovery*: once it surfaces a company/role,
verify it live on the company surface per Phase 3a/4 (prefer the ATS JSON API), and pull the
location from the ATS, not Built In's label.

---

## General High-Signal Sources (use for any domain)

These are the ATS platforms themselves, search them directly with domain keywords to find
roles that don't appear on LinkedIn or Indeed. When a company is on the Phase 2 target list,
prefer hitting its specific ATS subdomain/JSON feed directly per Phase 3a (that counts as
company-page verification); `ats_probe.py` automates resolving which of these a company uses.

- **Greenhouse**: site:greenhouse.io · **Lever**, site:lever.co · **Ashby**, site:jobs.ashbyhq.com
- **Workable**: site:apply.workable.com · **Jobvite**, site:jobvite.com
- **SmartRecruiters**: site:jobs.smartrecruiters.com · **BambooHR**, site:bamboohr.com/jobs
- **Rippling**: ats.rippling.com · **Comeet**, comeet.com/jobs
- Enterprise (common in IT/healthcare/finance/gov, often no clean public JSON: verify on the
  branded page): **Workday**, **iCIMS**, **SuccessFactors (SAP)**, **Oracle Cloud/Taleo**.
