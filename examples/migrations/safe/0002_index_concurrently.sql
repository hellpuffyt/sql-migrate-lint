-- Build the index without blocking writes.
SET lock_timeout = '2s';

CREATE INDEX CONCURRENTLY idx_users_email ON users (email);
