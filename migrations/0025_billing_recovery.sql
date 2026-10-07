BEGIN;

-- Historical intents cannot be reclassified as definitely unsent. Backfill this
-- receipt only while introducing the column; reapplying must preserve new unsent
-- intents whose process stopped before claiming Init.
DO $$
DECLARE
    tenant uuid;
    prior_context text := current_setting('omnicio.user_id', true);
    introducing_receipt boolean;
BEGIN
    introducing_receipt := NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'billing_payments'
          AND column_name = 'init_started_at'
    );
    IF introducing_receipt THEN
        ALTER TABLE billing_payments ADD COLUMN init_started_at timestamptz;
    END IF;
    ALTER TABLE billing_payments ADD COLUMN IF NOT EXISTS checkout_expires_at timestamptz;
    -- The production migration role owns this table but cannot bypass FORCE RLS.
    -- Include inactive users: their historical intents are not provably unsent.
    FOR tenant IN SELECT id FROM users LOOP
        PERFORM set_config('omnicio.user_id', tenant::text, true);
        IF introducing_receipt THEN
            UPDATE billing_payments SET init_started_at = created_at WHERE user_id = tenant;
        END IF;
        UPDATE billing_payments SET checkout_expires_at = created_at + interval '90 days'
            WHERE user_id = tenant AND checkout_expires_at IS NULL;
    END LOOP;
    PERFORM set_config('omnicio.user_id', COALESCE(prior_context, ''), true);
END
$$;
-- Old application processes can still insert while the additive migration is
-- installed. Only the new code explicitly inserts NULL before its I/O receipt.
ALTER TABLE billing_payments ALTER COLUMN init_started_at SET DEFAULT now();

ALTER TABLE billing_payments ALTER COLUMN checkout_expires_at SET NOT NULL;
ALTER TABLE billing_payments ALTER COLUMN checkout_expires_at
    SET DEFAULT (now() + interval '90 days');
ALTER TABLE billing_payments ADD COLUMN IF NOT EXISTS absence_checked_at timestamptz;
ALTER TABLE billing_payments ADD COLUMN IF NOT EXISTS resolution text;
ALTER TABLE billing_payments DROP CONSTRAINT IF EXISTS billing_payments_resolution_known;
ALTER TABLE billing_payments ADD CONSTRAINT billing_payments_resolution_known
    CHECK (resolution IS NULL OR resolution IN (
        'initialization_not_started', 'provider_order_absent'
    ));
ALTER TABLE billing_payments DROP CONSTRAINT IF EXISTS billing_payments_checkout_expiry_valid;
ALTER TABLE billing_payments ADD CONSTRAINT billing_payments_checkout_expiry_valid
    CHECK (checkout_expires_at > created_at);

COMMIT;
