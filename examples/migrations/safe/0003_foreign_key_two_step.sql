-- Two-step foreign key addition: add unvalidated (fast lock), then validate
-- separately (does not block writes).
SET lock_timeout = '2s';

ALTER TABLE orders
  ADD CONSTRAINT fk_orders_user
  FOREIGN KEY (user_id) REFERENCES users (id)
  NOT VALID;

ALTER TABLE orders VALIDATE CONSTRAINT fk_orders_user;
