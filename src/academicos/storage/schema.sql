PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', '4');

CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    term TEXT NOT NULL,
    section TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_courses_identity
    ON courses(term, code, COALESCE(section, ''));

CREATE TABLE IF NOT EXISTS source_items (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    course_id TEXT REFERENCES courses(id) ON DELETE SET NULL,
    source_url TEXT,
    source_timestamp TEXT,
    fetched_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    raw_text TEXT,
    raw_json TEXT,
    UNIQUE(source_type, source_id)
);

CREATE INDEX IF NOT EXISTS idx_source_items_course ON source_items(course_id);
CREATE INDEX IF NOT EXISTS idx_source_items_timestamp ON source_items(source_timestamp);

CREATE TABLE IF NOT EXISTS sync_state (
    source_key TEXT PRIMARY KEY,
    cursor TEXT,
    last_success_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS source_health (
    source_key TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_attempt_at TEXT NOT NULL,
    last_success_at TEXT,
    last_error TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0 CHECK (consecutive_failures >= 0),
    items_changed INTEGER NOT NULL DEFAULT 0 CHECK (items_changed >= 0),
    items_unchanged INTEGER NOT NULL DEFAULT 0 CHECK (items_unchanged >= 0),
    downloaded_files INTEGER NOT NULL DEFAULT 0 CHECK (downloaded_files >= 0),
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_source_health_status
    ON source_health(status, last_success_at);

CREATE TABLE IF NOT EXISTS file_manifest (
    source_key TEXT PRIMARY KEY,
    local_path TEXT NOT NULL,
    remote_fingerprint TEXT,
    local_sha256 TEXT,
    size_bytes INTEGER CHECK (size_bytes IS NULL OR size_bytes >= 0),
    etag TEXT,
    last_modified TEXT,
    last_checked_at TEXT NOT NULL,
    last_downloaded_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_file_manifest_path
    ON file_manifest(local_path);

CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY,
    source_item_id TEXT NOT NULL REFERENCES source_items(id) ON DELETE CASCADE,
    excerpt TEXT NOT NULL,
    field_path TEXT
);

CREATE TABLE IF NOT EXISTS course_sessions (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    session_type TEXT NOT NULL,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    location TEXT,
    delivery_mode TEXT
);

CREATE INDEX IF NOT EXISTS idx_course_sessions_course ON course_sessions(course_id);

CREATE TABLE IF NOT EXISTS candidate_events (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    course_id TEXT REFERENCES courses(id) ON DELETE SET NULL,
    target_ref TEXT,
    effective_at TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS candidate_evidence (
    candidate_event_id TEXT NOT NULL REFERENCES candidate_events(id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES evidence(id) ON DELETE CASCADE,
    PRIMARY KEY(candidate_event_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS event_overrides (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES course_sessions(id) ON DELETE CASCADE,
    effective_date TEXT NOT NULL,
    kind TEXT NOT NULL,
    new_start_at TEXT,
    new_end_at TEXT,
    new_location TEXT,
    new_delivery_mode TEXT,
    candidate_event_id TEXT REFERENCES candidate_events(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_event_overrides_session_date
    ON event_overrides(session_id, effective_date);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    course_id TEXT REFERENCES courses(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    task_type TEXT NOT NULL,
    due_at TEXT,
    initial_estimate_minutes INTEGER NOT NULL DEFAULT 0 CHECK (initial_estimate_minutes >= 0),
    remaining_minutes INTEGER NOT NULL DEFAULT 0 CHECK (remaining_minutes >= 0),
    actual_spent_minutes INTEGER NOT NULL DEFAULT 0 CHECK (actual_spent_minutes >= 0),
    progress REAL NOT NULL DEFAULT 0.0 CHECK (progress >= 0.0 AND progress <= 1.0),
    importance REAL NOT NULL DEFAULT 0.5 CHECK (importance >= 0.0 AND importance <= 1.0),
    status TEXT NOT NULL DEFAULT 'pending',
    origin_candidate_event_id TEXT REFERENCES candidate_events(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_course_due ON tasks(course_id, due_at);

CREATE TABLE IF NOT EXISTS plan_blocks (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'planned',
    pinned INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1)),
    planner_run_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_plan_blocks_time ON plan_blocks(start_at, end_at);

CREATE TABLE IF NOT EXISTS activity_feed (
    id TEXT PRIMARY KEY,
    course_id TEXT REFERENCES courses(id) ON DELETE SET NULL,
    source_item_id TEXT REFERENCES source_items(id) ON DELETE SET NULL,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    occurred_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
