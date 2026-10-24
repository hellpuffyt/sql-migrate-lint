SET lock_timeout = '2s';
ALTER TABLE events ADD COLUMN uid uuid NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE events ADD COLUMN seq bigserial;
ALTER TABLE events ADD COLUMN double_n int GENERATED ALWAYS AS (n * 2) STORED;
