UPDATE users SET email_verified = false WHERE id BETWEEN 1 AND 10000 AND email_verified IS NULL;
DELETE FROM sessions WHERE expires_at < now() - interval '30 days';
