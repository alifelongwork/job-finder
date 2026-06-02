-- Job Pipeline Database schema
-- See database.md for the contract. Created/managed only via jobsdb.py.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS candidates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    slug                TEXT UNIQUE NOT NULL,
    name                TEXT NOT NULL,
    email               TEXT,
    location_constraint TEXT,
    citizenship         TEXT,
    clearance           TEXT,
    comp_floor          INTEGER,
    comp_target         INTEGER,
    resume_path         TEXT,
    notes               TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_categories (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    rank         INTEGER NOT NULL,          -- 1 = highest priority
    label        TEXT NOT NULL,
    keywords     TEXT,
    UNIQUE(candidate_id, label)
);

CREATE TABLE IF NOT EXISTS companies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT UNIQUE NOT NULL,
    careers_url  TEXT,
    ats_platform TEXT,                       -- greenhouse|lever|ashby|workable|jobvite|smartrecruiters|other
    ats_slug     TEXT,
    multi_region INTEGER NOT NULL DEFAULT 0, -- boolean 0/1
    warm_path    TEXT,
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS jobs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id      INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    company_id        INTEGER REFERENCES companies(id),
    dedup_key         TEXT NOT NULL,
    title             TEXT NOT NULL,
    url               TEXT,
    ats_platform      TEXT,
    ats_job_id        TEXT,
    location          TEXT,                  -- actual city/state from the ATS
    remote_type       TEXT,                  -- onsite|hybrid|remote|unknown
    location_match    INTEGER,               -- boolean 0/1 (Phase 4c)
    comp_min          INTEGER,
    comp_max          INTEGER,
    posting_date      TEXT,                  -- ISO 8601 or NULL
    verification_tag  TEXT NOT NULL,         -- verified|wrong_location|aggregator|unverified
    tier              INTEGER,               -- 1|2|3|NULL
    category_label    TEXT,
    fit_summary       TEXT,
    screening_risks   TEXT,
    status            TEXT NOT NULL DEFAULT 'new',  -- new|active|applied|expired|rejected|ignored
    first_seen        TEXT NOT NULL,
    last_seen         TEXT NOT NULL,
    last_verified     TEXT,
    applied_date      TEXT,
    resume_path       TEXT,
    cover_letter_path TEXT,
    notes             TEXT,
    UNIQUE(candidate_id, dedup_key)
);

CREATE INDEX IF NOT EXISTS idx_jobs_candidate ON jobs(candidate_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status    ON jobs(candidate_id, status);
CREATE INDEX IF NOT EXISTS idx_jobs_tier      ON jobs(candidate_id, tier);

CREATE TABLE IF NOT EXISTS contacts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    name         TEXT,
    title        TEXT,
    priority     TEXT,                       -- ★★★ | ★★ | ★
    contact_type TEXT,
    hook         TEXT,
    action       TEXT,
    confirmed    INTEGER NOT NULL DEFAULT 0,
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS search_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
    run_date     TEXT NOT NULL,
    num_found    INTEGER,
    num_new      INTEGER,
    num_updated  INTEGER,
    num_expired  INTEGER,
    notes        TEXT
);
