-- Add a nullable column with no default: metadata-only change on Postgres,
-- safe on every supported version.
SET lock_timeout = '2s';

ALTER TABLE users ADD COLUMN middle_name text;
