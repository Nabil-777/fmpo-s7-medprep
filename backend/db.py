"""SQLite schema and database helpers for the S7 FMPO Study Platform."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "s7_platform.db"

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS modules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    short_name TEXT NOT NULL,
    sub_disciplines TEXT NOT NULL,
    exam_format TEXT NOT NULL,
    exam_duration_min INTEGER NOT NULL,
    scoring_rule TEXT NOT NULL,
    accent_color TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id TEXT NOT NULL,
    sub_discipline TEXT NOT NULL,
    professor TEXT NOT NULL,
    canonical_title TEXT NOT NULL,
    raw_tracker_title TEXT,
    promo_status TEXT NOT NULL DEFAULT 'none',
    upload_flag TEXT NOT NULL DEFAULT 'ok',
    row_order INTEGER NOT NULL DEFAULT 0,
    mastery_score REAL NOT NULL DEFAULT 0.0,
    reps INTEGER NOT NULL DEFAULT 0,
    lapses INTEGER NOT NULL DEFAULT 0,
    last_reviewed_at TEXT,
    next_review_at TEXT,
    high_yield_points TEXT NOT NULL DEFAULT '[]',
    notes_markdown TEXT NOT NULL DEFAULT '',
    exam_frequency TEXT NOT NULL DEFAULT 'normal'
);

CREATE TABLE IF NOT EXISTS drive_files (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    modified_time TEXT,
    module_id TEXT,
    category TEXT NOT NULL,
    professor TEXT,
    course_id INTEGER,
    local_path TEXT,
    text_chars INTEGER NOT NULL DEFAULT 0,
    page_count INTEGER NOT NULL DEFAULT 0,
    is_scanned INTEGER NOT NULL DEFAULT 0,
    is_corrige INTEGER NOT NULL DEFAULT 0,
    version_tag TEXT,
    extracted_preview TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_key TEXT UNIQUE NOT NULL,
    module_id TEXT NOT NULL,
    sub_discipline TEXT NOT NULL,
    course_id INTEGER,
    professor TEXT,
    source_file_id TEXT,
    source_label TEXT NOT NULL,
    exam_year TEXT,
    session TEXT NOT NULL,
    question_number INTEGER,
    vignette_group_id TEXT,
    vignette_text TEXT,
    question_type TEXT NOT NULL,
    stem TEXT NOT NULL,
    statements_json TEXT NOT NULL DEFAULT '[]',
    options_json TEXT NOT NULL DEFAULT '[]',
    correct_answers_json TEXT NOT NULL DEFAULT '[]',
    rubric_json TEXT NOT NULL DEFAULT '{}',
    explanation TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    scan_page_image TEXT,
    recurrence_count INTEGER NOT NULL DEFAULT 1,
    frequency_tag TEXT NOT NULL DEFAULT 'standard'
);

CREATE TABLE IF NOT EXISTS question_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    user_answer_json TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    partial_score REAL NOT NULL DEFAULT 0.0,
    max_score REAL NOT NULL DEFAULT 1.0,
    confidence TEXT,
    answered_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS clinical_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    module_id TEXT NOT NULL,
    sub_discipline TEXT NOT NULL,
    course_id INTEGER,
    title TEXT NOT NULL,
    difficulty TEXT NOT NULL DEFAULT 'Intermédiaire',
    source_tag TEXT NOT NULL,
    patient_summary TEXT NOT NULL,
    vitals_json TEXT NOT NULL DEFAULT '{}',
    steps_json TEXT NOT NULL,
    takeaway_points TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS clinical_case_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    score REAL NOT NULL,
    max_score REAL NOT NULL,
    answers_json TEXT NOT NULL DEFAULT '{}',
    completed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scan_jobs (
    id TEXT PRIMARY KEY,
    source_file_id TEXT,
    filename TEXT NOT NULL,
    module_id TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'examen',
    page_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'ready',
    pages_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_courses_module ON courses(module_id);
CREATE INDEX IF NOT EXISTS idx_files_module ON drive_files(module_id);
CREATE INDEX IF NOT EXISTS idx_files_course ON drive_files(course_id);
CREATE INDEX IF NOT EXISTS idx_q_module ON questions(module_id);
CREATE INDEX IF NOT EXISTS idx_q_course ON questions(course_id);
CREATE INDEX IF NOT EXISTS idx_q_source ON questions(source_label);
CREATE INDEX IF NOT EXISTS idx_q_type ON questions(question_type);
CREATE INDEX IF NOT EXISTS idx_attempts_q ON question_attempts(question_id);
"""


def get_conn(db_path: Path | None = None) -> sqlite3.Connection:
    """Open SQLite connection with row_factory enabled."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Initialize schema tables and indexes idempotently."""
    conn = get_conn(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def rows_to_dicts(rows: list[sqlite3.Row], json_fields: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    """Convert sqlite3.Row list into plain dicts, decoding JSON columns."""
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        for field in json_fields:
            raw = item.get(field)
            if isinstance(raw, str):
                try:
                    item[field] = json.loads(raw)
                except json.JSONDecodeError:
                    pass
        out.append(item)
    return out
