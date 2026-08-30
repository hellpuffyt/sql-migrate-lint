-- Blocks writes on `users` for the duration of the index build.
CREATE INDEX idx_users_email ON users (email);
