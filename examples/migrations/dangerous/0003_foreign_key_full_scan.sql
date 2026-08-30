-- Scans and locks the full `orders` table to validate the new constraint.
ALTER TABLE orders
  ADD CONSTRAINT fk_orders_user
  FOREIGN KEY (user_id) REFERENCES users (id);
