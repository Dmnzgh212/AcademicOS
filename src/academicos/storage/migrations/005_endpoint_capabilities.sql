CREATE TABLE IF NOT EXISTS endpoint_capabilities (
    source_key TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    status TEXT NOT NULL,
    http_status INTEGER,
    last_checked_at TEXT NOT NULL,
    next_probe_at TEXT,
    response_shape_json TEXT NOT NULL DEFAULT '{}',
    last_error TEXT,
    PRIMARY KEY(source_key, endpoint)
);

CREATE INDEX IF NOT EXISTS idx_endpoint_capabilities_probe
    ON endpoint_capabilities(status, next_probe_at);

UPDATE schema_meta SET value = '5' WHERE key = 'schema_version';
