-- A brand-new table and its indexes: nothing can be locked out yet.
CREATE TABLE invoices (
    id bigint PRIMARY KEY,
    customer_id bigint NOT NULL,
    total_cents bigint NOT NULL DEFAULT 0,
    note text DEFAULT 'where; drop table x'
);
CREATE INDEX invoices_customer_id_idx ON invoices (customer_id);
ALTER TABLE invoices ADD CONSTRAINT invoices_total_positive CHECK (total_cents >= 0);
