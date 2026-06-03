#!/usr/bin/env python3
"""Regression suite for jobsdb.py — drives the real CLI against a throwaway DB.

Run:  python test_jobsdb.py
Uses JOBSDB_PATH to point at a temp database so the real jobs.db is never touched.
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
JOBSDB = os.path.join(HERE, "jobsdb.py")
TMPDB = os.path.join(tempfile.gettempdir(), "jobsdb_test.db")
ENV = {**os.environ, "JOBSDB_PATH": TMPDB, "PYTHONIOENCODING": "utf-8"}

passed = failed = 0


def run(*args, expect_ok=True):
    r = subprocess.run([sys.executable, JOBSDB, *args], env=ENV,
                       capture_output=True, text=True, encoding="utf-8")
    if expect_ok and r.returncode != 0:
        raise AssertionError(f"cmd failed: {' '.join(args)}\n{r.stderr}")
    if not expect_ok and r.returncode == 0:
        raise AssertionError(f"cmd should have failed but didn't: {' '.join(args)}")
    return r


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def db():
    c = sqlite3.connect(TMPDB)
    c.row_factory = sqlite3.Row
    return c


def write_json(name, obj):
    path = os.path.join(tempfile.gettempdir(), name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return path


# ---------------------------------------------------------------------------
if os.path.exists(TMPDB):
    os.remove(TMPDB)

print("== init ==")
run("init")
check("init creates db", os.path.exists(TMPDB))
tables = {r[0] for r in db().execute("SELECT name FROM sqlite_master WHERE type='table'")}
check("6 core tables exist",
      {"candidates", "candidate_categories", "companies", "jobs", "contacts",
       "search_runs"} <= tables, tables)
r = run("init")  # idempotent, no --force
check("re-init does not clobber", "already exists" in r.stdout)

print("== candidate ==")
run("candidate", "add", "--slug", "tester", "--field", "name=Test User",
    "--field", "comp_floor=$120,000", "--field", "email=t@x.com")
row = db().execute("SELECT * FROM candidates WHERE slug='tester'").fetchone()
check("candidate added", row is not None)
check("comp_floor parsed from '$120,000'", row and row["comp_floor"] == 120000,
      row["comp_floor"] if row else None)
run("candidate", "add", "--slug", "tester", "--field", "comp_target=150000")
row = db().execute("SELECT * FROM candidates WHERE slug='tester'").fetchone()
check("candidate update is idempotent (no dup)",
      db().execute("SELECT count(*) FROM candidates").fetchone()[0] == 1)
check("update set comp_target", row["comp_target"] == 150000)
check("update preserved name", row["name"] == "Test User")
run("candidate", "add", "--slug", "bad", "--field", "nonsense=1", expect_ok=False)
check("unknown field rejected", True)

print("== category ==")
cats = write_json("cats.json", [
    {"rank": 1, "label": "Quantum", "keywords": "qiskit"},
    {"rank": 2, "label": "General SWE", "keywords": "python"},
])
run("category", "set", "--candidate", "tester", "--json", cats)
check("2 categories set",
      db().execute("SELECT count(*) FROM candidate_categories").fetchone()[0] == 2)
cats2 = write_json("cats2.json", [{"rank": 1, "label": "Only One"}])
run("category", "set", "--candidate", "tester", "--json", cats2)
check("category set replaces (not appends)",
      db().execute("SELECT count(*) FROM candidate_categories").fetchone()[0] == 1)

print("== upsert-batch: dedup keys ==")
batch1 = write_json("b1.json", {
    "candidate": "tester", "run_date": "2026-05-01", "jobs": [
        {"company": "A", "dedup_key": "greenhouse:a:1", "title": "Supplied Key",
         "url": "u1", "location": "Boulder, CO", "location_match": True,
         "verification_tag": "verified", "tier": 1, "category_label": "Quantum",
         "posting_date": "2026-04-01"},
        {"company": "B", "ats_platform": "lever", "ats_slug": "b", "ats_job_id": "2",
         "title": "Computed Key", "url": "u2", "location": "Remote",
         "location_match": True, "verification_tag": "verified", "tier": 2,
         "category_label": "Quantum", "posting_date": "2026-04-15"},
        {"company": "C", "title": "Agg Fallback Key", "url": "u3",
         "location": "Denver, CO", "location_match": True,
         "verification_tag": "aggregator", "tier": 3, "category_label": "General SWE"},
        {"company": "D", "dedup_key": "workable:d:9", "title": "Wrong Loc",
         "url": "u4", "location": "London, UK", "location_match": False,
         "verification_tag": "wrong_location", "category_label": "Quantum"},
    ]})
r = run("upsert-batch", batch1)
check("batch1 reports 4 new", json.loads(r.stdout.splitlines()[0]) ==
      {"found": 4, "new": 4, "updated": 0})
keys = {r["title"]: r["dedup_key"] for r in db().execute("SELECT title,dedup_key FROM jobs")}
check("computed key built", keys.get("Computed Key") == "lever:b:2", keys)
check("agg fallback key built", keys.get("Agg Fallback Key", "").startswith("agg:"), keys)

print("== upsert-batch: dedup + monotonic timestamps ==")
batch2 = write_json("b2.json", {
    "candidate": "tester", "run_date": "2026-05-31", "jobs": [
        {"company": "A", "dedup_key": "greenhouse:a:1", "title": "Supplied Key",
         "url": "u1", "location": "Boulder, CO", "location_match": True,
         "verification_tag": "verified", "tier": 1, "category_label": "Quantum",
         "posting_date": "2026-04-01", "comp_min": 100000, "comp_max": 140000},
        {"company": "C", "title": "Agg Fallback Key", "url": "u3",
         "location": "Denver, CO", "location_match": True,
         "verification_tag": "aggregator", "tier": 3, "category_label": "General SWE"},
    ]})
r = run("upsert-batch", batch2)
check("batch2 updates not dupes", json.loads(r.stdout.splitlines()[0]) ==
      {"found": 2, "new": 0, "updated": 2})
check("total rows still 4 (no duplication)",
      db().execute("SELECT count(*) FROM jobs").fetchone()[0] == 4)
ja = db().execute("SELECT * FROM jobs WHERE dedup_key='greenhouse:a:1'").fetchone()
check("metadata refreshed (comp)", ja["comp_min"] == 100000)
check("last_verified moved forward to run_date", ja["last_verified"] == "2026-05-31")
check("status new->active on re-sight", ja["status"] == "active")

# back-dated replay must NOT move timestamps backward
run("upsert-batch", batch1)  # run_date 2026-05-01 again
ja = db().execute("SELECT * FROM jobs WHERE dedup_key='greenhouse:a:1'").fetchone()
check("monotonic: last_verified not pushed back", ja["last_verified"] == "2026-05-31",
      ja["last_verified"])
check("monotonic: last_seen not pushed back", ja["last_seen"] == "2026-05-31",
      ja["last_seen"])

print("== company warm_path + multi_region stickiness ==")
# Isolated candidate so job-count assertions for 'tester' below are unaffected.
run("candidate", "add", "--slug", "wptester", "--field", "name=WP Tester")
wp1 = write_json("wp1.json", {
    "candidate": "wptester", "run_date": "2026-05-31", "jobs": [
        {"company": "WarmCo", "dedup_key": "greenhouse:warmco:1", "title": "WP Role",
         "url": "uwp", "location": "Boulder, CO", "location_match": True,
         "verification_tag": "verified", "tier": 1, "category_label": "Quantum",
         "multi_region": True, "warm_path": "Ex-colleague Dana is staff eng here"}]})
run("upsert-batch", wp1)
co = db().execute("SELECT * FROM companies WHERE name='WarmCo'").fetchone()
check("warm_path persisted", co["warm_path"] == "Ex-colleague Dana is staff eng here", co["warm_path"])
check("multi_region set", co["multi_region"] == 1, co["multi_region"])
# Re-upsert the same company WITHOUT multi_region/warm_path — neither must be cleared.
wp2 = write_json("wp2.json", {
    "candidate": "wptester", "run_date": "2026-06-01", "jobs": [
        {"company": "WarmCo", "dedup_key": "greenhouse:warmco:1", "title": "WP Role",
         "url": "uwp", "location": "Boulder, CO", "location_match": True,
         "verification_tag": "verified", "tier": 1, "category_label": "Quantum"}]})
run("upsert-batch", wp2)
co = db().execute("SELECT * FROM companies WHERE name='WarmCo'").fetchone()
check("multi_region sticky (not cleared by later scan)", co["multi_region"] == 1, co["multi_region"])
check("warm_path not clobbered by later scan", co["warm_path"] == "Ex-colleague Dana is staff eng here", co["warm_path"])

print("== company rename / merge ==")
run("candidate", "add", "--slug", "cotester", "--field", "name=CO Tester")
def _cojob(company, key):
    return {"company": company, "dedup_key": key, "title": "R", "url": "u" + key,
            "location": "Boulder, CO", "location_match": True,
            "verification_tag": "verified", "tier": 2, "category_label": "X"}
cr1 = write_json("cr1.json", {"candidate": "cotester", "run_date": "2026-05-31",
    "jobs": [_cojob("OldName Inc", "workday:old:r1"), _cojob("OldAlias", "workday:old:r2")]})
run("upsert-batch", cr1)
n_named = lambda: db().execute(
    "SELECT COUNT(*) FROM companies WHERE name IN "
    "('OldName Inc','OldAlias','BrandNew Lab')").fetchone()[0]
check("two distinct company rows created", n_named() == 2, n_named())
# simple rename (no existing target) + careers_url update
run("company", "rename", "--from", "OldName Inc", "--to", "BrandNew Lab",
    "--careers-url", "https://new.example/CAREERS")
row = db().execute("SELECT * FROM companies WHERE name='BrandNew Lab'").fetchone()
check("simple rename applied", row is not None)
check("rename updated careers_url",
      row and row["careers_url"] == "https://new.example/CAREERS",
      row["careers_url"] if row else None)
check("old name gone after rename",
      db().execute("SELECT COUNT(*) FROM companies WHERE name='OldName Inc'").fetchone()[0] == 0)
j1 = db().execute("SELECT co.name FROM jobs j JOIN companies co ON co.id=j.company_id "
                  "WHERE j.dedup_key='workday:old:r1'").fetchone()
check("job stays linked through rename", j1 and j1["name"] == "BrandNew Lab",
      j1["name"] if j1 else None)
# merge: rename OldAlias -> BrandNew Lab (target already exists) => repoint + drop dup
run("company", "rename", "--from", "OldAlias", "--to", "BrandNew Lab")
check("duplicate row removed on merge",
      db().execute("SELECT COUNT(*) FROM companies WHERE name='OldAlias'").fetchone()[0] == 0)
brand = db().execute("SELECT id FROM companies WHERE name='BrandNew Lab'").fetchone()
on_brand = db().execute("SELECT COUNT(*) FROM jobs WHERE company_id=?",
                        (brand["id"],)).fetchone()[0]
check("both jobs repointed to merged company", on_brand == 2, on_brand)
check("exactly one BrandNew Lab row remains",
      db().execute("SELECT COUNT(*) FROM companies WHERE name='BrandNew Lab'").fetchone()[0] == 1)
run("company", "rename", "--from", "DoesNotExist", "--to", "Whatever", expect_ok=False)
r = run("company", "list")
check("company list runs and shows merged row", "BrandNew Lab" in r.stdout)

print("== query filters & sort ==")
r = run("query", "--candidate", "tester", "--format", "json")
jobs = json.loads(r.stdout)
check("query returns all 4", len(jobs) == 4)
order = [j["title"] for j in jobs]
check("sort: tier1 first, wrong-loc last",
      order[0] == "Supplied Key" and order[-1] == "Wrong Loc", order)
check("tier filter", len(json.loads(
    run("query", "--candidate", "tester", "--tier", "1", "--format", "json").stdout)) == 1)
check("category filter", len(json.loads(
    run("query", "--candidate", "tester", "--category", "Quantum",
        "--format", "json").stdout)) == 3)
check("verification filter", len(json.loads(
    run("query", "--candidate", "tester", "--verification", "aggregator",
        "--format", "json").stdout)) == 1)
check("location-match=no filter", len(json.loads(
    run("query", "--candidate", "tester", "--location-match", "no",
        "--format", "json").stdout)) == 1)
check("limit", len(json.loads(
    run("query", "--candidate", "tester", "--limit", "2", "--format", "json").stdout)) == 2)

print("== reverify list ==")
r = run("reverify", "list", "--candidate", "tester", "--format", "json")
rv_titles = {j["title"] for j in json.loads(r.stdout)}
# Agg (never verified) is always stale (last_verified IS NULL).
check("aggregator (never company-confirmed) is stale", "Agg Fallback Key" in rv_titles, rv_titles)
# Tier 1/2 are re-checked regardless of the staleness window, as long as they weren't
# verified TODAY. 'Supplied Key' (tier1) and 'Computed Key' (tier2) were verified on past
# run_dates, so even a huge window must still surface them.
r = run("reverify", "list", "--candidate", "tester", "--stale-days", "365", "--format", "json")
wide = {j["title"] for j in json.loads(r.stdout)}
check("tier1/2 re-checked regardless of window (not verified today)",
      "Supplied Key" in wide and "Computed Key" in wide, wide)
# A wrong_location (tier null) verified within the window must NOT be force-surfaced.
check("non-tier1/2 within window not force-rechecked", "Wrong Loc" not in wide, wide)
# After verifying a tier-1 TODAY, the today-guard keeps it off the list.
run("mark", str(ja["id"]), "--verified")
r = run("reverify", "list", "--candidate", "tester", "--stale-days", "365", "--format", "json")
wide2 = {j["title"] for j in json.loads(r.stdout)}
check("tier1 verified today is not re-listed", "Supplied Key" not in wide2, wide2)
# wrong_location was confirmed live on the company surface -> it SETS last_verified
# (unlike aggregator, which never was, so its last_verified stays null).
wl = db().execute("SELECT last_verified FROM jobs WHERE title='Wrong Loc'").fetchone()[0]
agg = db().execute("SELECT last_verified FROM jobs WHERE title='Agg Fallback Key'").fetchone()[0]
check("wrong_location sets last_verified (live-confirmed)", wl is not None, wl)
check("aggregator leaves last_verified null (needs re-check)", agg is None, agg)

print("== mark transitions ==")
agg_id = db().execute("SELECT id FROM jobs WHERE title='Agg Fallback Key'").fetchone()[0]
run("mark", str(agg_id), "--status", "expired")
check("mark expired", db().execute("SELECT status FROM jobs WHERE id=?",
      (agg_id,)).fetchone()[0] == "expired")
r = run("reverify", "list", "--candidate", "tester", "--format", "json")
check("expired job drops off reverify list",
      agg_id not in {j["id"] for j in json.loads(r.stdout)})
# Default query/export hide expired/rejected/ignored; --all and explicit --status reveal them.
ids_default = {j["id"] for j in json.loads(
    run("query", "--candidate", "tester", "--format", "json").stdout)}
check("query hides expired by default", agg_id not in ids_default, ids_default)
ids_all = {j["id"] for j in json.loads(
    run("query", "--candidate", "tester", "--all", "--format", "json").stdout)}
check("query --all includes expired", agg_id in ids_all, ids_all)
ids_exp = {j["id"] for j in json.loads(
    run("query", "--candidate", "tester", "--status", "expired", "--format", "json").stdout)}
check("query --status expired still works", agg_id in ids_exp, ids_exp)
a_id = ja["id"]
run("mark", str(a_id), "--status", "applied", "--resume", "r.docx",
    "--cover", "c.docx", "--note", "submitted")
ja = db().execute("SELECT * FROM jobs WHERE id=?", (a_id,)).fetchone()
check("mark applied sets status", ja["status"] == "applied")
check("mark applied auto-sets applied_date", bool(ja["applied_date"]))
check("mark attaches resume path", ja["resume_path"] == "r.docx")
check("mark attaches cover path", ja["cover_letter_path"] == "c.docx")
check("mark appends note", "submitted" in (ja["notes"] or ""))

print("== terminal status preservation ==")
run("upsert-batch", batch2)  # includes job A as verified again
ja = db().execute("SELECT * FROM jobs WHERE id=?", (a_id,)).fetchone()
check("re-upsert preserves 'applied'", ja["status"] == "applied", ja["status"])

print("== error handling ==")
run("query", "--candidate", "ghost", expect_ok=False)
check("unknown candidate errors", True)
bad_tag = write_json("bad.json", {"candidate": "tester", "jobs": [
    {"company": "X", "dedup_key": "x:1", "title": "T", "verification_tag": "bogus"}]})
run("upsert-batch", bad_tag, expect_ok=False)
check("invalid verification_tag rejected", True)
run("mark", "99999", "--status", "applied", expect_ok=False)
check("mark nonexistent job errors", True)
run("mark", str(a_id), expect_ok=False)
check("mark with no fields errors", True)

print("== stats ==")
r = run("stats", "--candidate", "tester")
check("stats runs", "Pipeline for Test User" in r.stdout)

print("== export ==")
expbase = os.path.join(tempfile.gettempdir(), "jobsdb_export_test")
run("export", "--candidate", "tester", "--format", "csv", "--out", expbase)
csv_path = expbase + ".csv"
check("csv export written", os.path.exists(csv_path))
if os.path.exists(csv_path):
    txt = open(csv_path, encoding="utf-8").read()
    check("csv has header + data rows", txt.startswith("id,tier,status") and txt.count("\n") >= 4)
run("export", "--candidate", "tester", "--format", "md", "--out", expbase)
md_path = expbase + ".md"
check("md export written", os.path.exists(md_path))
if os.path.exists(md_path):
    md = open(md_path, encoding="utf-8").read()
    check("md is a tiered report", "# Job Opportunities" in md and "Tier 1" in md)
    check("md surfaces excluded wrong-location", "Excluded — Wrong Location" in md)
run("export", "--candidate", "tester", "--format", "all", "--out", expbase)
check("export all writes csv+md", os.path.exists(csv_path) and os.path.exists(md_path))
# filter passthrough: tier-1 only export has fewer data rows than full
run("export", "--candidate", "tester", "--format", "csv", "--tier", "1", "--out", expbase + "_t1")
t1 = open(expbase + "_t1.csv", encoding="utf-8").read()
check("export honors filters (tier=1)", t1.count("\n") < txt.count("\n"))
# default export hides expired (agg_id was expired above); --all reveals it
run("export", "--candidate", "tester", "--format", "csv", "--out", expbase + "_def")
deftxt = open(expbase + "_def.csv", encoding="utf-8").read()
check("export hides expired by default", "expired" not in deftxt)
run("export", "--candidate", "tester", "--all", "--format", "csv", "--out", expbase + "_allx")
allx = open(expbase + "_allx.csv", encoding="utf-8").read()
check("export --all includes expired", "expired" in allx)
for p in (csv_path, md_path, expbase + ".docx", expbase + "_t1.csv",
          expbase + "_def.csv", expbase + "_allx.csv"):
    if os.path.exists(p):
        os.remove(p)

# ---------------------------------------------------------------------------
print(f"\n{'='*40}\n{passed} passed, {failed} failed")
# Close any lingering inline connections so Windows releases the file lock.
import gc
gc.collect()
try:
    if os.path.exists(TMPDB):
        os.remove(TMPDB)
except OSError:
    pass  # temp file; OS will reclaim it
sys.exit(1 if failed else 0)
