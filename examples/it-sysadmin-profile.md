# Worked Example — IT / Systems Administrator candidate

A second worked example (alongside the quantum/SWE one) showing how the copilot adapts to a
**non-engineering, experienced** candidate. This is illustrative — a real candidate's brief
comes from their resume + the onboarding questionnaire, stored in the DB.

## Example brief (what onboarding would capture)

- **Profile:** ~8 yrs IT — helpdesk → desktop support → systems administrator. Windows
  Server, Active Directory, M365/Azure AD, VMware/Hyper-V, networking (VLANs, firewalls),
  backup/DR, PowerShell scripting, ticketing (ServiceNow). CompTIA A+/Network+/Security+;
  working toward Azure Administrator (AZ-104).
- **Citizenship/clearance:** US Citizen; no clearance (eligible to obtain).
- **Location:** e.g. "Denver metro — hybrid or onsite within 30 min, or fully remote US."
- **Comp:** floor 85k, target 100k.
- **Seniority + YOE:** targeting **Sysadmin / IT Administrator / Infrastructure** (mid),
  open to **IT Lead / Team Lead**; 8 yrs actual. (Over-leveled "IT Manager/Director" roles
  get surfaced but flagged as reaches; junior "helpdesk" roles flagged as under-leveled.)
- **Notes:** prefers stable internal-IT over MSP churn; avoid pure call-center helpdesk.

## Ranked categories (drives the search)

```json
[
  {"rank": 1, "label": "Systems / Infrastructure Administration",
   "keywords": "systems administrator, infrastructure engineer, windows administrator, active directory, vmware"},
  {"rank": 2, "label": "Cloud / DevOps Operations",
   "keywords": "azure administrator, cloud operations, m365 administrator, devops, intune"},
  {"rank": 3, "label": "IT Lead / Team Lead",
   "keywords": "it lead, infrastructure lead, it team lead, it operations"}
]
```

## Company categories to target (Phase 2a)

MSPs & managed-IT providers · healthcare & hospital systems · universities & K-12 districts ·
financial-services & insurance IT · state/local government · datacenter/colocation & cloud
operators · internal IT of large local employers (manufacturing, retail HQs, utilities).

## What's different from the quantum/SWE example

- **ATS mix skews enterprise.** Internal IT departments disproportionately run **Workday,
  iCIMS, SuccessFactors, Oracle/Taleo** — so the ATS Cookbook's Workday CXS path and
  branded-careers-page verification matter more than the lightweight Greenhouse/Lever GET
  feeds. `ats_probe.py` will resolve the lightweight ones; expect more `careers_only` /
  `unverified` company-verify outcomes that you confirm on the branded page.
- **Boards differ:** Dice and ClearanceJobs over Wellfound/HN; see `domain-boards.md`
  → "IT / Systems Administration".
- **Experienced, not early-career:** the seniority gate flags *under*-leveled helpdesk roles,
  the mirror of the quantum example flagging *over*-leveled PhD/Staff roles.

## Quick start for this candidate

```
# (own DB, so it doesn't mix with another candidate's pipeline)
$env:JOBSDB_PATH = "C:\path\to\itadmin_jobs.db"   # PowerShell;  export JOBSDB_PATH=... on mac/linux
python jobsdb.py init
# then in Claude Code: "Read Project_Instructions.md and be my job copilot. Resume: <path>."
```
