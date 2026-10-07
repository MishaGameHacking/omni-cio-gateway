BEGIN;

-- Private, explicitly user-supplied research evidence is never a public market authority.
CREATE TABLE IF NOT EXISTS strategy_research_evidence (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    version integer NOT NULL CHECK (version > 0),
    document jsonb NOT NULL CHECK (jsonb_typeof(document) = 'object'),
    received_at timestamptz NOT NULL DEFAULT now(),
    CHECK (octet_length(document::text) <= 1048576)
);

CREATE TABLE IF NOT EXISTS strategy_research_runs (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    id uuid NOT NULL,
    account_id text NOT NULL,
    environment text NOT NULL CHECK (environment IN ('prod', 'sandbox')),
    strategy_version integer NOT NULL CHECK (strategy_version > 0),
    evidence_version integer NOT NULL CHECK (evidence_version >= 0),
    data_hash text NOT NULL CHECK (data_hash ~ '^[0-9a-f]{64}$'),
    result jsonb NOT NULL CHECK (jsonb_typeof(result) = 'object'),
    inputs jsonb NOT NULL CHECK (jsonb_typeof(inputs) = 'object'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, id),
    CHECK (octet_length(result::text) <= 4194304),
    CHECK (octet_length(inputs::text) <= 4194304)
);
CREATE INDEX IF NOT EXISTS strategy_research_runs_recent
    ON strategy_research_runs (user_id, created_at DESC);

ALTER TABLE strategy_research_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_research_evidence FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS strategy_research_evidence_tenant ON strategy_research_evidence;
CREATE POLICY strategy_research_evidence_tenant ON strategy_research_evidence
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);
ALTER TABLE strategy_research_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_research_runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS strategy_research_runs_tenant ON strategy_research_runs;
CREATE POLICY strategy_research_runs_tenant ON strategy_research_runs
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

COMMIT;
