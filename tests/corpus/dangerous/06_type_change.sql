SET lock_timeout = '2s';
ALTER TABLE users ALTER COLUMN age TYPE bigint;
ALTER TABLE users ALTER COLUMN code TYPE text USING code::text;
