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

CREATE INDEX IF NOT EXISTS idx_source_health_status
    ON source_health(status, last_success_at);

CREATE INDEX IF NOT EXISTS idx_file_manifest_path
    ON file_manifest(local_path);

UPDATE schema_meta SET value = '4' WHERE key = 'schema_version';
