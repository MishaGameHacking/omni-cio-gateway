BEGIN;

-- Preserve readable replay inputs for a diversified, at-most-100-instrument run.
-- The application additionally enforces a per-owner aggregate archive budget
-- under the existing tenant advisory lock, regardless of subscription state.
DO $$
DECLARE
    old_bound record;
BEGIN
    -- PostgreSQL assigns names to the original unnamed column checks. Select
    -- only their original size expressions and retain JSON shape/tenant checks.
    FOR old_bound IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'strategy_research_runs'::regclass AND contype = 'c'
          AND pg_get_constraintdef(oid) LIKE '%octet_length%4194304%'
    LOOP
        EXECUTE format('ALTER TABLE strategy_research_runs DROP CONSTRAINT %I', old_bound.conname);
    END LOOP;
END $$;
ALTER TABLE strategy_research_runs DROP CONSTRAINT IF EXISTS strategy_research_runs_result_size;
ALTER TABLE strategy_research_runs DROP CONSTRAINT IF EXISTS strategy_research_runs_inputs_size;
ALTER TABLE strategy_research_runs ADD CONSTRAINT strategy_research_runs_result_size
    CHECK (octet_length(result::text) <= 33554432);
ALTER TABLE strategy_research_runs ADD CONSTRAINT strategy_research_runs_inputs_size
    CHECK (octet_length(inputs::text) <= 33554432);

DO $$
DECLARE
    old_bound record;
BEGIN
    FOR old_bound IN
        SELECT conname FROM pg_constraint
        WHERE conrelid = 'strategy_research_evidence'::regclass AND contype = 'c'
          AND pg_get_constraintdef(oid) LIKE '%octet_length%1048576%'
    LOOP
        EXECUTE format('ALTER TABLE strategy_research_evidence DROP CONSTRAINT %I', old_bound.conname);
    END LOOP;
END $$;
ALTER TABLE strategy_research_evidence DROP CONSTRAINT IF EXISTS strategy_research_evidence_size;
ALTER TABLE strategy_research_evidence ADD CONSTRAINT strategy_research_evidence_size
    CHECK (octet_length(document::text) <= 16777216);

CREATE TABLE IF NOT EXISTS strategy_research_requests (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    id uuid NOT NULL,
    input_hash text NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'expired', 'deleted')),
    run_id uuid,
    error_code text CHECK (error_code IS NULL OR error_code ~ '^[a-z_]{1,100}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL DEFAULT (clock_timestamp() + interval '10 minutes'),
    PRIMARY KEY (user_id, id),
    FOREIGN KEY (user_id, run_id) REFERENCES strategy_research_runs(user_id, id),
    CHECK ((status = 'completed') = (run_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS strategy_research_requests_recent
    ON strategy_research_requests(user_id, created_at DESC, id DESC);
ALTER TABLE strategy_research_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_research_requests FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS strategy_research_requests_tenant ON strategy_research_requests;
CREATE POLICY strategy_research_requests_tenant ON strategy_research_requests
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

COMMIT;
