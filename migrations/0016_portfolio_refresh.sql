BEGIN;

-- Manual observations have no scheduled date. Keep the accepted full unique
-- key so the previous application can still claim daily jobs after rollback.
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS requested_at timestamptz;
ALTER TABLE job_runs ALTER COLUMN scheduled_for DROP NOT NULL;

-- The table owner is also subject to FORCE RLS. Visit every server-owned
-- identity, including inactive users, without changing the tenant policies.
DO $omnicio$
DECLARE
    tenant_id uuid;
    previous_context text := current_setting('omnicio.user_id', true);
BEGIN
    FOR tenant_id IN SELECT id FROM users LOOP
        PERFORM set_config('omnicio.user_id', tenant_id::text, true);
        UPDATE job_runs
        SET requested_at = COALESCE(requested_at, started_at),
            scheduled_for = CASE
                WHEN job_type = 'portfolio_refresh' THEN NULL
                ELSE scheduled_for
            END
        WHERE user_id = tenant_id
          AND (requested_at IS NULL
               OR (job_type = 'portfolio_refresh' AND scheduled_for IS NOT NULL));
    END LOOP;
    PERFORM set_config('omnicio.user_id', COALESCE(previous_context, ''), true);
END;
$omnicio$;

ALTER TABLE job_runs ALTER COLUMN requested_at SET DEFAULT now();
ALTER TABLE job_runs ALTER COLUMN requested_at SET NOT NULL;

ALTER TABLE job_runs DROP CONSTRAINT IF EXISTS job_runs_status_check;
ALTER TABLE job_runs ADD CONSTRAINT job_runs_status_check
    CHECK (status IN ('queued', 'running', 'succeeded', 'degraded', 'failed'));
ALTER TABLE job_runs DROP CONSTRAINT IF EXISTS job_runs_finish_state_consistent;
ALTER TABLE job_runs ADD CONSTRAINT job_runs_finish_state_consistent CHECK (
    (status IN ('queued', 'running') AND finished_at IS NULL)
    OR (status NOT IN ('queued', 'running') AND finished_at IS NOT NULL)
);
ALTER TABLE job_runs DROP CONSTRAINT IF EXISTS job_runs_schedule_kind_consistent;
ALTER TABLE job_runs ADD CONSTRAINT job_runs_schedule_kind_consistent CHECK (
    (job_type = 'portfolio_refresh' AND scheduled_for IS NULL)
    OR (job_type <> 'portfolio_refresh' AND scheduled_for IS NOT NULL)
);

-- Restore the original key if an earlier unreleased candidate was applied.
-- Default NULL-distinct uniqueness permits independent unscheduled runs while
-- preserving the old ON CONFLICT (user_id, job_type, scheduled_for) statement.
DO $omnicio$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'job_runs'::regclass
          AND conname = 'job_runs_user_id_job_type_scheduled_for_key'
    ) THEN
        ALTER TABLE job_runs
            ADD CONSTRAINT job_runs_user_id_job_type_scheduled_for_key
            UNIQUE (user_id, job_type, scheduled_for);
    END IF;
END;
$omnicio$;
DROP INDEX IF EXISTS job_runs_daily_identity_idx;
CREATE UNIQUE INDEX IF NOT EXISTS job_runs_refresh_active_idx
    ON job_runs (user_id)
    WHERE job_type = 'portfolio_refresh' AND status IN ('queued', 'running');
CREATE INDEX IF NOT EXISTS job_runs_refresh_requested_idx
    ON job_runs (user_id, requested_at DESC, started_at DESC)
    WHERE job_type = 'portfolio_refresh';

-- Existing FORCE RLS policies and user cascade continue to cover all new jobs.
COMMIT;
