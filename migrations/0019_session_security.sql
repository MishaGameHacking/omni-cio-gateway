BEGIN;

-- Old sessions remain usable, but cannot authorize identity removal until OAuth
-- is repeated. Authentication time does not slide with ordinary session refresh.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS authenticated_provider text;
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS authenticated_at timestamptz;
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conrelid = 'sessions'::regclass
        AND conname = 'sessions_authentication_evidence'
    ) THEN
        ALTER TABLE sessions ADD CONSTRAINT sessions_authentication_evidence CHECK (
            (authenticated_provider IS NULL AND authenticated_at IS NULL)
            OR (authenticated_provider IS NOT NULL
                AND authenticated_provider IN ('vkid', 'tid') AND authenticated_at IS NOT NULL)
        );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS sessions_expired_retention_idx ON sessions (expires_at);
CREATE INDEX IF NOT EXISTS sessions_revoked_retention_idx ON sessions (revoked_at)
    WHERE revoked_at IS NOT NULL;

COMMIT;
