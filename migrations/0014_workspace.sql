BEGIN;

CREATE TABLE IF NOT EXISTS workspace_preferences (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    version integer NOT NULL CHECK (version > 0),
    document jsonb NOT NULL CHECK (
        jsonb_typeof(document) = 'object' AND octet_length(document::text) <= 32768
    ),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS investment_goals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version integer NOT NULL CHECK (version > 0),
    title text NOT NULL CHECK (char_length(btrim(title)) BETWEEN 1 AND 120),
    kind text NOT NULL CHECK (kind IN ('capital', 'income')),
    target_amount_rub numeric(24, 8) NOT NULL CHECK (
        target_amount_rub > 0 AND target_amount_rub <= 1000000000000
    ),
    target_date date,
    start_date date NOT NULL,
    progress_source text NOT NULL CHECK (progress_source IN ('portfolio', 'income', 'manual')),
    allocation_percent numeric(12, 9),
    manual_amount_rub numeric(24, 8),
    status text NOT NULL CHECK (status IN ('active', 'completed', 'archived')),
    account_id text,
    environment text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, user_id),
    CHECK (target_date IS NULL OR target_date >= start_date),
    CHECK (
        (progress_source = 'manual' AND allocation_percent IS NULL
            AND manual_amount_rub >= 0 AND manual_amount_rub <= 1000000000000
            AND manual_amount_rub IS NOT NULL AND account_id IS NULL AND environment IS NULL)
        OR
        (progress_source IN ('portfolio', 'income') AND allocation_percent > 0
            AND allocation_percent <= 100 AND allocation_percent IS NOT NULL
            AND manual_amount_rub IS NULL AND account_id IS NOT NULL
            AND char_length(account_id) BETWEEN 1 AND 128
            AND environment IS NOT NULL AND environment IN ('prod', 'sandbox'))
    ),
    CHECK (progress_source = 'manual' OR (kind, progress_source) IN (
        ('capital', 'portfolio'), ('income', 'income')
    ))
);

CREATE INDEX IF NOT EXISTS investment_goals_user_status_idx
    ON investment_goals (user_id, status, created_at);

CREATE TABLE IF NOT EXISTS workspace_events (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    id text NOT NULL CHECK (id ~ '^[0-9a-f]{64}$'),
    category text NOT NULL CHECK (category IN ('portfolio', 'payments', 'goals', 'system')),
    kind text NOT NULL CHECK (char_length(kind) BETWEEN 1 AND 64),
    severity text NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
    detail text NOT NULL CHECK (char_length(detail) <= 1000),
    occurred_at timestamptz NOT NULL,
    read_at timestamptz,
    target text NOT NULL CHECK (target IN ('overview', 'portfolio', 'income', 'goals', 'settings')),
    source jsonb NOT NULL CHECK (
        jsonb_typeof(source) = 'object' AND octet_length(source::text) <= 4096
    ),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, id)
);

CREATE INDEX IF NOT EXISTS workspace_events_user_time_idx
    ON workspace_events (user_id, occurred_at DESC, id);
CREATE INDEX IF NOT EXISTS workspace_events_unread_idx
    ON workspace_events (user_id, occurred_at DESC) WHERE read_at IS NULL;

ALTER TABLE workspace_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_preferences FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS workspace_preferences_tenant ON workspace_preferences;
CREATE POLICY workspace_preferences_tenant ON workspace_preferences
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

ALTER TABLE investment_goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE investment_goals FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS investment_goals_tenant ON investment_goals;
CREATE POLICY investment_goals_tenant ON investment_goals
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

ALTER TABLE workspace_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS workspace_events_tenant ON workspace_events;
CREATE POLICY workspace_events_tenant ON workspace_events
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

COMMIT;
