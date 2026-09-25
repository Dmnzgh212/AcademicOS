ALTER TABLE courses ADD COLUMN section TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_courses_identity
    ON courses(term, code, COALESCE(section, ''));

UPDATE schema_meta SET value = '2' WHERE key = 'schema_version';
