SET lock_timeout = '2s';
ALTER TABLE accounts ADD COLUMN tier text NOT NULL DEFAULT 'free';
ALTER TABLE accounts ADD COLUMN created_at timestamptz NOT NULL DEFAULT now();
