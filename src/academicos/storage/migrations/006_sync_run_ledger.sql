CREATE TABLE IF NOT EXISTS sync_runs (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    status TEXT NOT NULL,
    source_count INTEGER NOT NULL DEFAULT 0 CHECK (source_count >= 0),
    ok_count INTEGER NOT NULL DEFAULT 0 CHECK (ok_count >= 0),
    partial_count INTEGER NOT NULL DEFAULT 0 CHECK (partial_count >= 0),
    failed_count INTEGER NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
    items_changed INTEGER NOT NULL DEFAULT 0 CHECK (items_changed >= 0),
    items_unchanged INTEGER NOT NULL DEFAULT 0 CHECK (items_unchanged >= 0),
    downloaded_files INTEGER NOT NULL DEFAULT 0 CHECK (downloaded_files >= 0)
);

CREATE INDEX IF NOT EXISTS idx_sync_runs_finished
    ON sync_runs(finished_at DESC);

CREATE TABLE IF NOT EXISTS sync_run_sources (
    run_id TEXT NOT NULL REFERENCES sync_runs(id) ON DELETE CASCADE,
    source_key TEXT NOT NULL,
    status TEXT NOT NULL,
    error_count INTEGER NOT NULL DEFAULT 0 CHECK (error_count >= 0),
    PRIMARY KEY(run_id, source_key)
);

CREATE INDEX IF NOT EXISTS idx_sync_run_sources_status
    ON sync_run_sources(status, source_key);

UPDATE schema_meta SET value = '6' WHERE key = 'schema_version';
