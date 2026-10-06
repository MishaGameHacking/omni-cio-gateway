BEGIN;

-- Manual observations are independent durable runs. Daily jobs keep their
-- existing date idempotency and every completed snapshot remains immutable.
ALTER TABLE job_runs ADD COLUMN IF NOT EXISTS requested_at timestamptz;
UPDATE job_runs SET requested_at = started_at WHERE requested_at IS NULL;
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
ALTER TABLE job_runs DROP CONSTRAINT IF EXISTS job_runs_user_id_job_type_scheduled_for_key;
CREATE UNIQUE INDEX IF NOT EXISTS job_runs_daily_identity_idx
    ON job_runs (user_id, job_type, scheduled_for)
    WHERE job_type <> 'portfolio_refresh';
CREATE UNIQUE INDEX IF NOT EXISTS job_runs_refresh_active_idx
    ON job_runs (user_id)
    WHERE job_type = 'portfolio_refresh' AND status IN ('queued', 'running');
CREATE INDEX IF NOT EXISTS job_runs_refresh_requested_idx
    ON job_runs (user_id, requested_at DESC, started_at DESC)
    WHERE job_type = 'portfolio_refresh';

-- Existing FORCE RLS policies and user cascade continue to cover all new jobs.
COMMIT;
