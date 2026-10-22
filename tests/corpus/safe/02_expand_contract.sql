SET lock_timeout = '2s';
SET statement_timeout = '15min';
ALTER TABLE users ADD COLUMN email_verified boolean;
CREATE INDEX CONCURRENTLY users_email_verified_idx ON users (email_verified);
ALTER TABLE orders ADD CONSTRAINT orders_user_fk FOREIGN KEY (user_id) REFERENCES users (id) NOT VALID;
ALTER TABLE orders VALIDATE CONSTRAINT orders_user_fk;
