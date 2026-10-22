SET lock_timeout = '2s';
ALTER TABLE orders ADD FOREIGN KEY (user_id) REFERENCES users (id);
ALTER TABLE orders ADD CHECK (amount > 0);
