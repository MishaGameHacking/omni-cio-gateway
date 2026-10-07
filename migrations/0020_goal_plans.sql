BEGIN;

CREATE TABLE IF NOT EXISTS goal_plans (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    goal_id uuid NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    document jsonb NOT NULL CHECK (
        jsonb_typeof(document) = 'object' AND octet_length(document::text) <= 4096
    ),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, goal_id),
    FOREIGN KEY (goal_id, user_id) REFERENCES investment_goals(id, user_id) ON DELETE CASCADE
);
ALTER TABLE goal_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE goal_plans FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS goal_plans_tenant ON goal_plans;
CREATE POLICY goal_plans_tenant ON goal_plans
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

COMMIT;
