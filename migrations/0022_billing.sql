BEGIN;

CREATE TABLE IF NOT EXISTS billing_payments (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    id uuid NOT NULL,
    order_id text NOT NULL UNIQUE CHECK (order_id ~ '^[0-9]{9}-[0-9a-f]{32}$'),
    terminal_key text NOT NULL CHECK (char_length(terminal_key) BETWEEN 1 AND 64),
    provider_payment_id text,
    amount_kopecks bigint NOT NULL CHECK (amount_kopecks BETWEEN 1 AND 100000000),
    period_days integer NOT NULL CHECK (period_days BETWEEN 1 AND 366),
    offer_version text NOT NULL CHECK (char_length(offer_version) BETWEEN 1 AND 64),
    status text NOT NULL CHECK (status IN (
        'creating', 'pending', 'paid', 'cancelled', 'refunded', 'partial_refund', 'uncertain'
    )),
    checkout_url text,
    entitlement_from timestamptz,
    entitlement_until timestamptz,
    cancel_attempted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, id),
    UNIQUE (terminal_key, provider_payment_id),
    CHECK ((entitlement_from IS NULL AND entitlement_until IS NULL)
        OR (entitlement_from IS NOT NULL AND entitlement_until IS NOT NULL
            AND entitlement_until > entitlement_from))
);
CREATE INDEX IF NOT EXISTS billing_payments_user_time_idx
    ON billing_payments(user_id, created_at DESC);
ALTER TABLE billing_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_payments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS billing_payments_tenant ON billing_payments;
CREATE POLICY billing_payments_tenant ON billing_payments
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

COMMIT;
