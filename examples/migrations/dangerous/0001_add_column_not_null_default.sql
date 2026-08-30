-- Rewrites the whole table on Postgres < 11: run with
-- `sql-migrate-lint --target-version 9.6` to see it flagged as an error,
-- or `--target-version 11+` to see it pass clean.
ALTER TABLE users ADD COLUMN age INT NOT NULL DEFAULT 0;
