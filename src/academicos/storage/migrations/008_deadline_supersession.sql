-- Some migration tests and very early AcademicOS databases can have schema_meta
-- without every v1 table present. Recreate the v7 candidate table shape only when
-- it is missing so v8 can still migrate forward safely.
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

ALTER TABLE candidate_events
    ADD COLUMN superseded_by_candidate_id TEXT REFERENCES candidate_events(id) ON DELETE SET NULL;
ALTER TABLE candidate_events ADD COLUMN superseded_at TEXT;
ALTER TABLE candidate_events ADD COLUMN rolled_back_at TEXT;

ALTER TABLE task_deadline_changes ADD COLUMN status TEXT NOT NULL DEFAULT 'applied';
ALTER TABLE task_deadline_changes
    ADD COLUMN supersedes_change_id TEXT REFERENCES task_deadline_changes(id) ON DELETE SET NULL;
ALTER TABLE task_deadline_changes ADD COLUMN superseded_at TEXT;
ALTER TABLE task_deadline_changes ADD COLUMN rolled_back_at TEXT;

-- Older databases may already contain more than one historical deadline change
-- for the same task. Treat only the most recent as currently applied.
UPDATE task_deadline_changes
SET status = 'superseded',
    superseded_at = COALESCE(applied_at, CURRENT_TIMESTAMP)
WHERE id IN (
    SELECT id
    FROM (
        SELECT
            id,
            ROW_NUMBER() OVER (
                PARTITION BY task_id
                ORDER BY applied_at DESC, id DESC
            ) AS position
        FROM task_deadline_changes
    )
    WHERE position > 1
);

CREATE INDEX IF NOT EXISTS idx_task_deadline_changes_status
    ON task_deadline_changes(task_id, status, applied_at DESC);
CREATE INDEX IF NOT EXISTS idx_candidate_supersession
    ON candidate_events(superseded_by_candidate_id, status);

INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', '8');
