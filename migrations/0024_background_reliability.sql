BEGIN;

-- A digest advances over server availability time, not the date reported by a
-- late broker operation. The nullable cursor lets existing channels retain their
-- last completed legacy period on first use, without replaying delivered history.
ALTER TABLE notification_channels ADD COLUMN IF NOT EXISTS digest_cursor_at timestamptz;
ALTER TABLE notification_outbox ADD COLUMN IF NOT EXISTS updated_at timestamptz;
CREATE INDEX IF NOT EXISTS workspace_events_user_available_idx
    ON workspace_events (user_id, updated_at, revision);

-- One dated root remains compatible with the accepted daily unique key. A retry
-- is a new run, so its immutable snapshot/evidence never borrow the failed run's
-- snapshot. Tenant-bound self references cannot point into another account.
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS retry_of uuid;
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz;
-- Preserve the age of already-pending work instead of making old failures or
-- stalled queues appear new at deployment. FORCE RLS also applies to the owner.
DO $omnicio$
DECLARE
    tenant_id uuid;
    previous_context text := current_setting('omnicio.user_id', true);
BEGIN
    FOR tenant_id IN SELECT id FROM users LOOP
        PERFORM set_config('omnicio.user_id', tenant_id::text, true);
        UPDATE notification_outbox
        SET updated_at = COALESCE(accepted_at, created_at)
        WHERE user_id = tenant_id AND updated_at IS NULL;
        UPDATE job_runs
        SET next_attempt_at = CASE
            WHEN status IN ('failed', 'degraded') THEN finished_at + interval '5 minutes'
            ELSE COALESCE(started_at, requested_at)
        END
        WHERE user_id = tenant_id AND next_attempt_at IS NULL;
    END LOOP;
    PERFORM set_config('omnicio.user_id', COALESCE(previous_context, ''), true);
END;
$omnicio$;
ALTER TABLE notification_outbox ALTER COLUMN updated_at SET DEFAULT clock_timestamp();
ALTER TABLE notification_outbox ALTER COLUMN updated_at SET NOT NULL;
DO $omnicio$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'notification_outbox'::regclass
                   AND conname = 'notification_outbox_owner_channel_id_key') THEN
        ALTER TABLE notification_outbox ADD CONSTRAINT notification_outbox_owner_channel_id_key
            UNIQUE (user_id, channel_id, id);
    END IF;
END;
$omnicio$;

-- A revision belongs to one delivery, independent of the current digest setting.
-- Historical accepted messages are not backfilled as event receipts: an older
-- aggregate did not preserve its exact membership. Runtime only adopts queued
-- messages under the existing owner lock, before preparing or sending new work.
CREATE TABLE IF NOT EXISTS notification_outbox_events (
    user_id uuid NOT NULL,
    channel_id uuid NOT NULL,
    event_id text NOT NULL,
    event_revision bigint NOT NULL CHECK (event_revision > 0),
    outbox_id uuid NOT NULL,
    PRIMARY KEY (user_id, channel_id, event_id, event_revision),
    FOREIGN KEY (user_id, channel_id, outbox_id)
        REFERENCES notification_outbox(user_id, channel_id, id) ON DELETE CASCADE,
    FOREIGN KEY (user_id, event_id)
        REFERENCES workspace_events(user_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS notification_outbox_events_message_idx
    ON notification_outbox_events (user_id, outbox_id);
ALTER TABLE notification_outbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_outbox_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS notification_outbox_events_tenant ON notification_outbox_events;
CREATE POLICY notification_outbox_events_tenant ON notification_outbox_events
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);
ALTER TABLE job_runs ALTER COLUMN next_attempt_at SET DEFAULT clock_timestamp();
ALTER TABLE job_runs ALTER COLUMN next_attempt_at SET NOT NULL;
DO $omnicio$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'job_runs'::regclass
                   AND conname = 'job_runs_user_id_id_key') THEN
        ALTER TABLE job_runs ADD CONSTRAINT job_runs_user_id_id_key UNIQUE (user_id, id);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'job_runs'::regclass
                   AND conname = 'job_runs_retry_owner_fkey') THEN
        ALTER TABLE job_runs ADD CONSTRAINT job_runs_retry_owner_fkey
            FOREIGN KEY (user_id, retry_of) REFERENCES job_runs(user_id, id) ON DELETE CASCADE;
    END IF;
END;
$omnicio$;
ALTER TABLE job_runs DROP CONSTRAINT IF EXISTS job_runs_schedule_kind_consistent;
ALTER TABLE job_runs ADD CONSTRAINT job_runs_schedule_kind_consistent CHECK (
    (job_type = 'portfolio_refresh' AND scheduled_for IS NULL AND retry_of IS NULL)
    OR (job_type = 'portfolio_daily' AND scheduled_for IS NULL AND retry_of IS NOT NULL)
    OR (job_type <> 'portfolio_refresh' AND scheduled_for IS NOT NULL AND retry_of IS NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS job_runs_daily_retry_attempt_idx
    ON job_runs (user_id, retry_of, attempt) WHERE retry_of IS NOT NULL;
CREATE INDEX IF NOT EXISTS job_runs_daily_pending_idx
    ON job_runs (user_id, next_attempt_at, requested_at)
    WHERE job_type = 'portfolio_daily' AND status IN ('queued', 'running');

-- Service-level evidence has no tenant identity, message, destination or secret.
-- The application aggregates these facts only through its server-owned operator
-- boundary; ordinary HTTP readiness remains a separate database/schema check.
CREATE TABLE IF NOT EXISTS worker_heartbeats (
    worker_name text PRIMARY KEY CHECK (
        worker_name IN ('notifications', 'portfolio_refresh', 'portfolio_daily')
    ),
    checked_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    status text NOT NULL CHECK (status IN ('running', 'ok', 'attention', 'stopped'))
);
ALTER TABLE worker_heartbeats ADD COLUMN IF NOT EXISTS completed_status text
    CHECK (completed_status IN ('ok', 'attention'));
UPDATE worker_heartbeats SET completed_status = status
    WHERE completed_status IS NULL AND status IN ('ok', 'attention');

COMMIT;
