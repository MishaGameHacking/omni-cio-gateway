BEGIN;

ALTER TABLE notification_channels ADD COLUMN IF NOT EXISTS session_id uuid;
ALTER TABLE notification_channels ADD COLUMN IF NOT EXISTS binding_id uuid;
ALTER TABLE notification_outbox ADD COLUMN IF NOT EXISTS binding_id uuid;

DO $omnicio$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'sessions'::regclass
                   AND conname = 'sessions_owner_id_key') THEN
        ALTER TABLE sessions ADD CONSTRAINT sessions_owner_id_key UNIQUE (user_id, id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conrelid = 'notification_channels'::regclass
                     AND conname = 'notification_channels_session_owner_fkey') THEN
        -- Pruning old sessions must retain delivery history. A detached channel
        -- is expired by status/queue/claim before it can be used again.
        ALTER TABLE notification_channels
            ADD CONSTRAINT notification_channels_session_owner_fkey
            FOREIGN KEY (user_id, session_id) REFERENCES sessions(user_id, id)
            ON DELETE SET NULL (session_id);
    END IF;
END;
$omnicio$;

-- No legacy push channel proves which session opted in. Expire every unbound
-- subscription, including all competing owners of a legacy endpoint. Do not
-- choose an owner or replay queued messages after a fresh browser opt-in.
DO $omnicio$
DECLARE
    tenant_id uuid;
    previous_context text := current_setting('omnicio.user_id', true);
BEGIN
    FOR tenant_id IN SELECT id FROM users LOOP
        PERFORM set_config('omnicio.user_id', tenant_id::text, true);
        UPDATE notification_channels
        SET status = 'expired', updated_at = clock_timestamp()
        WHERE user_id = tenant_id AND kind = 'push' AND status = 'active'
          AND (session_id IS NULL OR binding_id IS NULL);
        UPDATE notification_outbox AS o
        SET status = 'cancelled', last_error = 'push_binding_expired',
            updated_at = clock_timestamp()
        FROM notification_channels AS c
        WHERE o.user_id = tenant_id AND c.user_id = o.user_id AND c.id = o.channel_id
          AND c.kind = 'push' AND o.status = 'queued'
          AND (c.session_id IS NULL OR c.binding_id IS NULL);
    END LOOP;
    PERFORM set_config('omnicio.user_id', COALESCE(previous_context, ''), true);
END;
$omnicio$;

-- This unique index also arbitrates simultaneous opt-ins by different tenants.
-- Runtime handles its conflict without reading or modifying another owner.
CREATE UNIQUE INDEX IF NOT EXISTS notification_push_active_destination_key
    ON notification_channels (destination_hash) WHERE kind = 'push' AND status = 'active';
CREATE INDEX IF NOT EXISTS notification_channels_session_idx
    ON notification_channels (user_id, session_id) WHERE session_id IS NOT NULL;
ALTER TABLE notification_outbox DROP CONSTRAINT IF EXISTS notification_outbox_kind_check;
ALTER TABLE notification_outbox ADD CONSTRAINT notification_outbox_kind_check
    CHECK (kind IN ('event', 'digest', 'verification', 'operational', 'test'));
CREATE INDEX IF NOT EXISTS notification_outbox_test_rate_idx
    ON notification_outbox (user_id, created_at DESC) WHERE kind = 'test';

-- Operational server credentials, not tenant/device data. All runtime workers
-- reuse the same encrypted per-origin VAPID JWT; no endpoint path or user ID is
-- retained here. Identity is a hash of the public key and subject, never a secret.
CREATE TABLE IF NOT EXISTS notification_push_authorizations (
    origin text NOT NULL CHECK (char_length(origin) BETWEEN 9 AND 261
        AND origin ~ '^https://[a-z0-9.-]+$'),
    identity_hash text NOT NULL CHECK (identity_hash ~ '^[0-9a-f]{64}$'),
    issued_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    authorization_ciphertext bytea NOT NULL,
    PRIMARY KEY (origin, identity_hash),
    CHECK (expires_at > issued_at AND expires_at <= issued_at + interval '24 hours')
);

COMMIT;
