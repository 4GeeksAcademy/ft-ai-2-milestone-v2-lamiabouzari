-- Existing rfp_tickets rows keep their id. rfp_id is a separate business key.
ALTER TABLE rfp_tickets ADD COLUMN IF NOT EXISTS rfp_id VARCHAR;

UPDATE rfp_tickets
SET rfp_id = 'rfp_' || replace(gen_random_uuid()::text, '-', '')
WHERE rfp_id IS NULL OR rfp_id = '';

CREATE UNIQUE INDEX IF NOT EXISTS ux_rfp_tickets_rfp_id ON rfp_tickets (rfp_id);
