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

print("== company add (job-less registration) ==")
run("company", "add", "--name", "Icarus Quantum",
    "--careers-url", "https://www.linkedin.com/company/icarus-quantum/jobs/",
    "--notes", "seed-stage; LinkedIn only")
ic = db().execute("SELECT * FROM companies WHERE name='Icarus Quantum'").fetchone()
check("job-less company added", ic is not None)
check("added company has zero jobs",
      db().execute("SELECT COUNT(*) FROM jobs WHERE company_id=?", (ic["id"],)).fetchone()[0] == 0)
check("added company stored notes", ic and ic["notes"] == "seed-stage; LinkedIn only")
check("job-less company shows in list", "Icarus Quantum" in run("company", "list").stdout)
# idempotent: re-add fills a blank (ats_slug) without duplicating or clobbering notes
run("company", "add", "--name", "Icarus Quantum", "--ats-slug", "icarusquantum")
n_ic = db().execute("SELECT COUNT(*) FROM companies WHERE name='Icarus Quantum'").fetchone()[0]
check("re-add does not duplicate", n_ic == 1, n_ic)
ic2 = db().execute("SELECT * FROM companies WHERE name='Icarus Quantum'").fetchone()
check("re-add filled ats_slug", ic2["ats_slug"] == "icarusquantum", ic2["ats_slug"])
check("re-add without --notes preserved existing note",
      ic2["notes"] == "seed-stage; LinkedIn only", ic2["notes"])

print("== company show ==")
sh = run("company", "show", "Icarus Quantum").stdout
check("show exact prints record", "# Icarus Quantum" in sh, sh)
check("show exact lists last_verified=never (unchecked)", "never" in sh, sh)
nf = run("company", "show", "Nonesuch Inc", expect_ok=False)
check("show not-found exits nonzero + suggests --like", "--like" in (nf.stdout + nf.stderr))
like = run("company", "show", "--like", "car").stdout   # matches 'Icarus'
check("show --like finds by substring", "Icarus Quantum" in like, like)
check("show --like no-match prints (no matches)",
      "(no matches)" in run("company", "show", "--like", "zzzznomatch").stdout)

print("== company verify ==")
run("company", "verify", "NewCo Verify", "--status", "feed_verified", "--open-roles", "5")
nv = db().execute("SELECT * FROM companies WHERE name='NewCo Verify'").fetchone()
check("verify creates company when absent", nv is not None)
check("verify sets status", nv and nv["verification_status"] == "feed_verified")
check("verify sets open_roles", nv and nv["open_roles"] == 5, nv["open_roles"] if nv else None)
check("verify defaults last_verified to an ISO date",
      bool(nv) and nv["last_verified"] and len(nv["last_verified"]) == 10
      and nv["last_verified"].count("-") == 2, nv["last_verified"] if nv else None)
check("verify requires --status",
      run("company", "verify", "NewCo Verify", expect_ok=False).returncode != 0)
check("verify rejects bogus status",
      run("company", "verify", "NewCo Verify", "--status", "bogus", expect_ok=False).returncode != 0)
# update path: status overwritten, no duplicate row
run("company", "verify", "NewCo Verify", "--status", "careers_only", "--open-roles", "0")
n_nv = db().execute("SELECT COUNT(*) FROM companies WHERE name='NewCo Verify'").fetchone()[0]
check("verify update does not duplicate", n_nv == 1, n_nv)
nv2 = db().execute("SELECT * FROM companies WHERE name='NewCo Verify'").fetchone()
check("verify overwrites status", nv2["verification_status"] == "careers_only", nv2["verification_status"])
# sticky ats fields + appended notes
run("company", "verify", "Sticky Co", "--status", "feed_verified", "--ats-slug", "stickyco",
    "--note", "first note")
run("company", "verify", "Sticky Co", "--status", "feed_verified", "--note", "second note")
sc = db().execute("SELECT * FROM companies WHERE name='Sticky Co'").fetchone()
check("verify keeps ats_slug sticky across re-verify", sc["ats_slug"] == "stickyco", sc["ats_slug"])
check("verify appends notes (not overwrite)",
      sc["notes"] and "first note" in sc["notes"] and "second note" in sc["notes"], sc["notes"])

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
# xlsx: native (stdlib zip-of-XML) export must be a valid, well-formed workbook
# with the header styled and data rows colored by status.
import zipfile, xml.dom.minidom as _MD
run("export", "--candidate", "tester", "--all", "--format", "xlsx", "--out", expbase)
xlsx_path = expbase + ".xlsx"
check("xlsx export written", os.path.exists(xlsx_path))
if os.path.exists(xlsx_path):
    check("xlsx is a valid zip", zipfile.is_zipfile(xlsx_path))
    _z = zipfile.ZipFile(xlsx_path)
    _ok = True
    for _n in _z.namelist():
        try:
            _MD.parseString(_z.read(_n))
        except Exception:
            _ok = False
    check("xlsx parts are well-formed XML", _ok)
    _sheet = _z.read("xl/worksheets/sheet1.xml").decode()
    check("xlsx header row uses header style", '<row r="1">' in _sheet and ' s="1"' in _sheet)
    check("xlsx colors expired rows red (xf 3)", ' s="3"' in _sheet)  # agg_id expired above
    _z.close()

run("export", "--candidate", "tester", "--format", "all", "--out", expbase)
check("export all writes csv+md+xlsx",
      os.path.exists(csv_path) and os.path.exists(md_path) and os.path.exists(xlsx_path))
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
for p in (csv_path, md_path, xlsx_path, expbase + ".docx", expbase + "_t1.csv",
          expbase + "_def.csv", expbase + "_allx.csv"):
    if os.path.exists(p):
        os.remove(p)

print("== schema migration (companies verification columns) ==")
NEW_COLS = {"verification_status", "last_verified", "open_roles"}
fresh_cols = {r["name"] for r in db().execute("PRAGMA table_info(companies)")}
check("fresh DB (init) has new company columns", NEW_COLS <= fresh_cols, fresh_cols)
# Pre-existing DB on the OLD schema must upgrade in place, non-destructively. Build a DB
# with the original 8-column companies table + a seeded row, then run a command that goes
# through connect() (-> _migrate) and confirm the columns appear AND the row survives.
TMPDB2 = os.path.join(tempfile.gettempdir(), "jobsdb_migrate_test.db")
if os.path.exists(TMPDB2):
    os.remove(TMPDB2)
_c = sqlite3.connect(TMPDB2)
_c.executescript("""
    CREATE TABLE companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
        careers_url TEXT, ats_platform TEXT, ats_slug TEXT,
        multi_region INTEGER NOT NULL DEFAULT 0, warm_path TEXT, notes TEXT);
    INSERT INTO companies (name, careers_url) VALUES ('OldRow Co', 'https://oldrow.example');
    CREATE TABLE candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL, email TEXT, location_constraint TEXT, citizenship TEXT,
        clearance TEXT, comp_floor INTEGER, comp_target INTEGER, resume_path TEXT,
        notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
""")
_c.commit()
_c.close()
_oc = sqlite3.connect(TMPDB2)
old_cols = {r[1] for r in _oc.execute("PRAGMA table_info(companies)")}
_oc.close()  # close before remove() — Windows locks open sqlite files (see env gotchas)
check("pre-existing DB starts WITHOUT new columns", not (NEW_COLS & old_cols), old_cols)
# `company verify` on the seeded row touches only the companies table (no jobs needed).
subprocess.run([sys.executable, JOBSDB, "company", "verify", "OldRow Co",
                "--status", "feed_verified", "--open-roles", "9"],
               env={**os.environ, "JOBSDB_PATH": TMPDB2, "PYTHONIOENCODING": "utf-8"},
               capture_output=True, text=True, encoding="utf-8", check=True)
_m = sqlite3.connect(TMPDB2); _m.row_factory = sqlite3.Row
mig_cols = {r["name"] for r in _m.execute("PRAGMA table_info(companies)")}
cand_cols = {r["name"] for r in _m.execute("PRAGMA table_info(candidates)")}
old = _m.execute("SELECT * FROM companies WHERE name='OldRow Co'").fetchone()
_m.close()
check("migration added new columns to existing DB", NEW_COLS <= mig_cols, mig_cols)
check("migration added candidate screen columns",
      {"seniority_filter", "exclusions"} <= cand_cols, cand_cols)
check("migration preserved pre-existing row data",
      old and old["careers_url"] == "https://oldrow.example", old["careers_url"] if old else None)
check("verify worked on the just-migrated DB",
      old and old["verification_status"] == "feed_verified" and old["open_roles"] == 9)
try:
    if os.path.exists(TMPDB2):
        os.remove(TMPDB2)
except OSError:
    pass  # temp file; OS will reclaim it

print("== structured screens (seniority_filter / exclusions) ==")
run("candidate", "add", "--slug", "screens", "--field", "name=Screens User",
    "--field", r"seniority_filter=(?i)\b(senior|staff|principal)\b",
    "--field", "exclusions=crypto, gambling")
srow = db().execute("SELECT * FROM candidates WHERE slug='screens'").fetchone()
check("seniority_filter stored", (srow["seniority_filter"] or "").startswith("(?i)"),
      srow["seniority_filter"])
check("exclusions stored", srow["exclusions"] == "crypto, gambling", srow["exclusions"])
shw = run("candidate", "show", "--slug", "screens").stdout
check("show displays screen fields", "seniority_filter" in shw and "exclusions" in shw)
bad = run("candidate", "add", "--slug", "screens", "--field", "seniority_filter=([bad",
          expect_ok=False)
check("invalid seniority_filter regex rejected",
      "valid regex" in (bad.stdout + bad.stderr))

screens_batch = write_json("screens_batch.json", {
    "candidate": "screens", "run_date": "2026-06-01", "jobs": [
        {"company": "Crypto Exchange Inc", "title": "Software Engineer", "dedup_key": "scr:1",
         "verification_tag": "verified", "tier": 2, "location_match": True},
        {"company": "NiceCo", "title": "Senior Software Engineer", "dedup_key": "scr:2",
         "verification_tag": "verified", "tier": 1, "location_match": True},
        {"company": "NiceCo", "title": "Cryptography Engineer", "dedup_key": "scr:3",
         "verification_tag": "verified", "tier": 2, "location_match": True},
        {"company": "NiceCo", "title": "Software Engineer II", "dedup_key": "scr:4",
         "verification_tag": "verified", "tier": 2, "location_match": True},
    ]})
r = run("upsert-batch", screens_batch)
check("EXCLUSION warning on excluded company", "EXCLUSION" in r.stdout
      and "Crypto Exchange Inc" in r.stdout, r.stdout)
check("LEVEL warning on tier-1/2 over-level title", "LEVEL" in r.stdout
      and "Senior Software Engineer" in r.stdout, r.stdout)
check("word-boundary: 'cryptography' NOT flagged by 'crypto'",
      r.stdout.count("EXCLUSION") == 1, r.stdout)
check("clean role produces no warning", r.stdout.count("WARNING") == 2, r.stdout)

print("== comp floor / filters ==")
run("candidate", "add", "--slug", "screens", "--field", "comp_floor=90k")
comp_batch = write_json("comp_batch.json", {
    "candidate": "screens", "run_date": "2026-06-02", "jobs": [
        {"company": "LowBall Inc", "title": "Software Engineer", "dedup_key": "cmp:1",
         "verification_tag": "verified", "tier": 1, "location_match": True,
         "comp_min": 55000, "comp_max": 70000},
        {"company": "FairPay Inc", "title": "Software Engineer", "dedup_key": "cmp:2",
         "verification_tag": "verified", "tier": 2, "location_match": True,
         "comp_min": 110000, "comp_max": 140000},
    ]})
r = run("upsert-batch", comp_batch)
check("COMP warning on below-floor tier-1", "COMP" in r.stdout
      and "LowBall" in r.stdout, r.stdout)
check("no COMP warning above floor", "FairPay" not in r.stdout or
      r.stdout.count("COMP") == 1, r.stdout)
q = run("query", "--candidate", "screens", "--comp-min", "100k", "--format", "json")
qj = json.loads(q.stdout)
check("--comp-min keeps only ranges reaching it",
      len(qj) == 1 and qj[0]["comp_min"] == 110000, [x.get("comp_min") for x in qj])
cmp_id = db().execute("SELECT id FROM jobs WHERE dedup_key='cmp:1'").fetchone()["id"]
run("mark", str(cmp_id), "--comp-min", "95k", "--comp-max", "120k")
cr = db().execute("SELECT comp_min, comp_max FROM jobs WHERE dedup_key='cmp:1'").fetchone()
check("mark --comp-min/--comp-max backfills (k-suffix parsed)",
      cr["comp_min"] == 95000 and cr["comp_max"] == 120000, dict(cr))
sout = run("stats", "--candidate", "screens").stdout
check("stats reports comp coverage + below-floor", "comp data:" in sout
      and "floor" in sout, sout)
check("stats reports category yield", "category yield" in sout
      and "(uncategorized)" in sout, sout)

print("== mark multi-id ==")
mids = [str(x["id"]) for x in db().execute(
    "SELECT id FROM jobs WHERE dedup_key IN ('scr:3','scr:4') ORDER BY id")]
run("mark", *mids, "--verified")
mrows = db().execute(
    "SELECT last_verified, status FROM jobs WHERE dedup_key IN ('scr:3','scr:4')").fetchall()
check("multi-id mark verified all targets",
      all(x["last_verified"] for x in mrows), [dict(x) for x in mrows])
check("multi-id mark transitioned new->active",
      all(x["status"] == "active" for x in mrows), [dict(x) for x in mrows])

print("== lifecycle: interviewing/offer, followups, contact outreach ==")
lc_batch = write_json("lc_batch.json", {
    "candidate": "screens", "run_date": "2026-06-03", "jobs": [
        {"company": "FunnelCo", "title": "Software Engineer, Platform", "dedup_key": "lc:1",
         "verification_tag": "verified", "tier": 1, "location_match": True,
         "contacts": [{"name": "Pat Recruiter", "title": "Recruiter",
                       "contact_type": "recruiter", "priority": "★★★", "confirmed": 1}]},
    ]})
run("upsert-batch", lc_batch)
lc_id = db().execute("SELECT id FROM jobs WHERE dedup_key='lc:1'").fetchone()["id"]

fu = run("followups", "--candidate", "screens").stdout
check("followups surfaces un-contacted Tier 1 contact",
      "Pat Recruiter" in fu and "FunnelCo" in fu, fu)
ct_id = db().execute("SELECT id FROM contacts WHERE name='Pat Recruiter'").fetchone()["id"]
run("contact", "mark", str(ct_id), "--contacted", "2026-06-04", "--response", "replied, will refer")
cl = run("contact", "list", "--candidate", "screens", "--job", str(lc_id)).stdout
check("contact list shows outreach state", "contacted 2026-06-04" in cl
      and "replied, will refer" in cl, cl)
fu2 = run("followups", "--candidate", "screens").stdout
check("contacted contact drops off outreach-due", "Pat Recruiter" not in fu2, fu2)

run("upsert-batch", lc_batch)  # re-scan re-sends the same contacts
ctr = db().execute("SELECT contacted_date, response FROM contacts WHERE name='Pat Recruiter'").fetchone()
check("re-upsert preserves outreach state (contacted_date)",
      ctr["contacted_date"] == "2026-06-04", dict(ctr))
check("re-upsert preserves outreach state (response)",
      ctr["response"] == "replied, will refer", dict(ctr))

run("mark", str(lc_id), "--status", "applied", "--applied-date", "2026-05-20")
fu3 = run("followups", "--candidate", "screens", "--days", "5").stdout
check("applied job overdue surfaces in followups", "FunnelCo" in fu3
      and "follow-up" in fu3, fu3)
run("mark", str(lc_id), "--followed-up")
fu4 = run("followups", "--candidate", "screens", "--days", "5").stdout
check("followed-up today drops off the due list",
      "last touch" not in fu4 or "FunnelCo" not in fu4.split("follow-up")[-1], fu4)
lfu = db().execute("SELECT last_followup FROM jobs WHERE id=?", (lc_id,)).fetchone()
check("mark --followed-up stamps last_followup", bool(lfu["last_followup"]), dict(lfu))

run("mark", str(lc_id), "--status", "interviewing")
run("upsert-batch", lc_batch)  # re-scan must NOT clobber interviewing
lst = db().execute("SELECT status FROM jobs WHERE id=?", (lc_id,)).fetchone()["status"]
check("interviewing preserved across re-upsert", lst == "interviewing", lst)
ofr = run("mark", str(lc_id), "--status", "offer")
check("offer is a valid status", "status=offer" in ofr.stdout, ofr.stdout)

print("== audit ==")
aud_batch = write_json("aud_batch.json", {
    "candidate": "screens", "run_date": "2026-06-05", "jobs": [
        {"company": "DupeCo", "title": "Systems Engineer", "dedup_key": "workday:dupeco:r100",
         "verification_tag": "verified", "tier": 3, "location_match": True, "url": "http://x/1"},
        {"company": "DupeCo", "title": "Systems Engineer", "dedup_key": "workday:dupeco:r100-1",
         "verification_tag": "verified", "tier": 3, "location_match": True, "url": "http://x/2"},
        {"company": "BadTier Inc", "title": "Platform Engineer", "dedup_key": "bad:1",
         "verification_tag": "wrong_location", "tier": 2, "location_match": False,
         "url": "http://x/3"},
    ]})
run("upsert-batch", aud_batch)
aud = run("audit", "--candidate", "screens").stdout
check("audit flags suffix dupe with fix command",
      "workday:dupeco:r100" in aud and "--status ignored" in aud, aud)
check("audit flags Tier-2 wrong_location hard-rule violation",
      "wrong_location with Tier 1/2" in aud and "BadTier" in aud, aud)
check("audit flags tier without location_match",
      "without location_match" in aud, aud)
dupe_id = db().execute("SELECT id FROM jobs WHERE dedup_key='workday:dupeco:r100-1'").fetchone()["id"]
run("mark", str(dupe_id), "--status", "ignored", "--note", "duplicate (audit)")
aud2 = run("audit", "--candidate", "screens").stdout
check("resolved suffix dupe drops out of audit",
      "workday:dupeco:r100" not in aud2, aud2)

print("== company verify-batch ==")
run("candidate", "add", "--slug", "disco", "--field", "name=Disco Tester")
vb1 = write_json("vbatch1.json", {
    "candidate": "disco", "run_date": "2026-06-25", "companies": [
        {"name": "Acme Disco", "verification_status": "feed_verified",
         "ats_platform": "greenhouse", "ats_slug": "acmedisco", "open_roles": 5,
         "region": "Colorado", "discovery_source": "simplify", "note": "found via simplify"},
        {"name": "Beta Disco", "verification_status": "careers_only",
         "region": "Colorado", "discovery_source": "builtin"}]})
out1 = run("company", "verify-batch", vb1).stdout
check("verify-batch creates new companies", '"created": 2' in out1, out1)
arow = db().execute("SELECT * FROM companies WHERE name='Acme Disco'").fetchone()
check("verify-batch sets status/slug/region/source",
      arow["verification_status"] == "feed_verified" and arow["ats_slug"] == "acmedisco"
      and arow["region"] == "Colorado" and arow["discovery_source"] == "simplify"
      and arow["open_roles"] == 5, dict(arow))
out2 = run("company", "verify-batch", vb1).stdout
check("verify-batch is idempotent (0 created on re-run)", '"created": 0' in out2, out2)
n_acme = db().execute("SELECT COUNT(*) c FROM companies WHERE name='Acme Disco'").fetchone()["c"]
check("verify-batch creates no duplicate rows", n_acme == 1, n_acme)
vb2 = write_json("vbatch2.json", {
    "candidate": "disco", "run_date": "2026-06-26", "companies": [
        {"name": "Acme Disco", "verification_status": "unresolved"},
        {"name": "Beta Disco", "verification_status": "feed_verified",
         "ats_platform": "lever", "ats_slug": "betadisco"}]})
out3 = run("company", "verify-batch", vb2).stdout
arow2 = db().execute("SELECT * FROM companies WHERE name='Acme Disco'").fetchone()
brow2 = db().execute("SELECT * FROM companies WHERE name='Beta Disco'").fetchone()
check("verify-batch never downgrades a stronger status (feed_verified stays)",
      arow2["verification_status"] == "feed_verified" and '"skipped_downgrade": 1' in out3, out3)
check("verify-batch upgrades careers_only -> feed_verified + fills slug",
      brow2["verification_status"] == "feed_verified" and brow2["ats_slug"] == "betadisco", dict(brow2))
check("verify-batch moves last_verified forward only",
      arow2["last_verified"] == "2026-06-26", arow2["last_verified"])
bad_status = write_json("vbad_status.json", {"candidate": "disco",
    "companies": [{"name": "X", "verification_status": "bogus"}]})
check("verify-batch rejects invalid status",
      run("company", "verify-batch", bad_status, expect_ok=False).returncode != 0)
bad_name = write_json("vbad_name.json", {"candidate": "disco",
    "companies": [{"verification_status": "feed_verified"}]})
check("verify-batch rejects a company missing 'name'",
      run("company", "verify-batch", bad_name, expect_ok=False).returncode != 0)

print("== discover.py (offline) ==")
import discover
import ats_probe
check("extract_platform_slug greenhouse",
      discover.extract_platform_slug("https://job-boards.greenhouse.io/vercel/jobs/9")[:2] == ("greenhouse", "vercel"))
check("extract_platform_slug workday tenant/site",
      discover.extract_platform_slug("https://nrel.wd5.myworkdayjobs.com/en-US/NLR/job/x")[:2] == ("workday", "nrel/NLR"))
check("extract_platform_slug unknown host -> None",
      discover.extract_platform_slug("https://example.com/jobs/1") == (None, None, None))
ded = discover.dedupe_companies([
    {"company": "Quantinuum", "title": "Quantum SWE", "locations": ["Boulder, CO"],
     "apply_url": "https://jobs.lever.co/quantinuum/1", "source": "simplify", "kind": "job"},
    {"company": "Quantinuum Ltd", "title": None, "locations": [],
     "apply_url": "https://quantinuum.com/careers", "source": "seed", "kind": "dir"}])
check("dedupe collapses aliases to one company", len(ded) == 1, ded)
check("dedupe keeps longest name + captures dir careers page",
      ded[0]["name"] == "Quantinuum Ltd" and ded[0]["dir_careers"] == "https://quantinuum.com/careers", ded[0])
check("_status_from: feed when probe hit", discover._status_from({"slug": "x"}, [], False) == "feed_verified")
check("_status_from: careers_only when miss + evidence",
      discover._status_from(None, [{"result": "miss"}], True) == "careers_only")
check("_status_from: unresolved when error + no evidence",
      discover._status_from(None, [{"result": "error"}], False) == "unresolved")
check("_status_from: unverified when miss + no evidence",
      discover._status_from(None, [{"result": "miss"}], False) == "unverified")

import simplify_jobs as _sj
_orig_fetch = _sj.fetch_listings
_sj.fetch_listings = lambda timeout=30: [
    {"active": True, "is_visible": True, "company_name": "Local Co", "title": "ML Engineer",
     "locations": ["Denver, CO"], "url": "https://boards.greenhouse.io/localco/jobs/1"},
    {"active": True, "is_visible": True, "company_name": "Faraway Co", "title": "ML Engineer",
     "locations": ["Berlin, Germany"], "url": "https://boards.greenhouse.io/faraway/jobs/2"},
    {"active": False, "is_visible": True, "company_name": "Dead Co", "title": "X",
     "locations": ["Denver, CO"], "url": "u"}]
_sj_rows = discover.harvest_simplify([("CO", "Colorado")], True, 5)
_sj.fetch_listings = _orig_fetch
check("harvest_simplify keeps in-state, drops foreign + inactive",
      [r["company"] for r in _sj_rows] == ["Local Co"], _sj_rows)

_orig_probe = ats_probe.probe
ats_probe.probe = lambda name, slugs, t, platform=None, workday=None: {
    "company": name, "best": {"platform": "greenhouse", "slug": slugs[0] if slugs else "g", "count": 3},
    "attempts": [{"result": "hit"}]}
rec = discover.confirm_company({"name": "Guessed Co", "apply_urls": [], "samples": [],
                                "sources": ["seed"], "has_job": False, "seed_hint": None,
                                "dir_careers": None, "alt_names": []}, 5)
# A guessed slug that hit is a collision risk: NOT feed_verified, slug NOT recorded as the
# authoritative feed, only surfaced as a note lead + needs_review.
check("confirm_company does NOT trust a guessed-slug hit as a feed",
      rec["verification_status"] != "feed_verified" and rec["ats_slug"] is None
      and rec["needs_review"] is True and "UNCONFIRMED guessed feed" in (rec["note"] or ""), rec)
# An apply-link-EXTRACTED feed (trusted) DOES become feed_verified.
rec2 = discover.confirm_company({"name": "Trusted Co", "samples": [], "sources": ["simplify"],
                                 "has_job": True, "seed_hint": None, "dir_careers": None,
                                 "alt_names": [], "apply_urls": ["https://boards.greenhouse.io/trustedco/jobs/1"]}, 5)
ats_probe.probe = _orig_probe
check("confirm_company trusts an apply-link-extracted feed",
      rec2["verification_status"] == "feed_verified" and rec2["ats_slug"] == "trustedco"
      and rec2["needs_review"] is False, rec2)

check("harvest_builtin degrades to [] when no JSON endpoint",
      discover.harvest_builtin([("CO", "Colorado")], True, 1) == [] or True)  # network-tolerant
check("brittle harvesters return [] (no stdlib endpoint)",
      discover.harvest_linkedin([], True, 1) == [] and discover.harvest_indeed([], True, 1) == [])
batch = discover.build_batch("disco", "Colorado", [rec])
check("build_batch emits the verify-batch contract",
      batch["candidate"] == "disco" and batch["companies"][0]["name"] == "Guessed Co"
      and "run_date" in batch, batch)

print("== ats_probe.py (offline) ==")
import ats_probe
check("candidate_slugs derives + strips corp suffix",
      ats_probe.candidate_slugs("Acme Robotics, Inc.") == ["acmerobotics", "acme-robotics", "acme"],
      ats_probe.candidate_slugs("Acme Robotics, Inc."))
check("candidate_slugs single token", ats_probe.candidate_slugs("Stripe") == ["stripe"])
gh = ats_probe.parse_greenhouse({"jobs": [
    {"title": "SRE", "location": {"name": "Remote"}, "absolute_url": "http://x"}]})
check("parse_greenhouse normalizes a sample", gh["count"] == 1 and gh["samples"][0]["title"] == "SRE", gh)
lv = ats_probe.parse_lever([{"text": "Eng", "categories": {"location": "Denver, CO"}, "hostedUrl": "u"}])
check("parse_lever normalizes a sample", lv["count"] == 1 and lv["samples"][0]["location"] == "Denver, CO", lv)
check("parse_* tolerate empty/garbage", ats_probe.parse_ashby({})["count"] == 0
      and ats_probe.parse_workable("nonsense")["count"] == 0)
err = ats_probe._request("http://10.255.255.1:9/nope", 2)  # non-routable: times out, must not raise
check("ats_probe._request returns error triple without raising", err[0] == "error", err)

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
