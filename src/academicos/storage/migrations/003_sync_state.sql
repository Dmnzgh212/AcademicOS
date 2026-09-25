CREATE TABLE IF NOT EXISTS sync_state (
    source_key TEXT PRIMARY KEY,
    cursor TEXT,
    last_success_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', '3');
