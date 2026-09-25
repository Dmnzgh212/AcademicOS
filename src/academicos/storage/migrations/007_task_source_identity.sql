CREATE TABLE IF NOT EXISTS task_source_links (
    source_type TEXT NOT NULL,
    source_key TEXT NOT NULL,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    source_item_id TEXT REFERENCES source_items(id) ON DELETE SET NULL,
    source_kind TEXT NOT NULL,
    external_id TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY(source_type, source_key)
);

CREATE INDEX IF NOT EXISTS idx_task_source_links_task
    ON task_source_links(task_id);

CREATE TABLE IF NOT EXISTS task_deadline_changes (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    candidate_event_id TEXT REFERENCES candidate_events(id) ON DELETE SET NULL,
    old_due_at TEXT,
    new_due_at TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_task_deadline_changes_task
    ON task_deadline_changes(task_id, applied_at DESC);

UPDATE schema_meta SET value = '7' WHERE key = 'schema_version';
