-- Irreversible operations with no backup note.
DROP TABLE legacy_sessions;

TRUNCATE audit_log;

UPDATE users SET last_login = NULL;
