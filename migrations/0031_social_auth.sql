BEGIN;

-- Pre-session identities, like vkid_identities and sessions, are server-only.
-- They grant no access to tenant business tables and accept no client-selected user ID.
CREATE TABLE IF NOT EXISTS telegram_identities (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    telegram_subject text NOT NULL UNIQUE CHECK (telegram_subject ~ '^[0-9]{1,128}$'),
    verified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS social_auth_flows (
    id uuid PRIMARY KEY,
    provider text NOT NULL CHECK (provider IN ('telegram', 'vkid')),
    purpose text NOT NULL CHECK (purpose IN ('login', 'link')),
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    session_digest bytea,
    flow_digest bytea NOT NULL CHECK (octet_length(flow_digest) = 32),
    state_digest bytea NOT NULL UNIQUE CHECK (octet_length(state_digest) = 32),
    secrets_ciphertext bytea,
    android_package text NOT NULL CHECK (android_package IN ('ru.omnicio.app', 'ru.omnicio.app.debug')),
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'exchanging', 'verified', 'failed', 'consumed')),
    subject text CHECK (subject ~ '^[0-9]{1,128}$'),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    CONSTRAINT social_flow_expiry CHECK (expires_at > created_at),
    CONSTRAINT social_flow_link CHECK (
        (purpose = 'link' AND user_id IS NOT NULL AND session_digest IS NOT NULL
            AND octet_length(session_digest) = 32)
        OR (purpose = 'login' AND session_digest IS NULL)
    ),
    CONSTRAINT social_flow_proof CHECK (status <> 'verified' OR subject IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS social_auth_flows_expiry_idx ON social_auth_flows (expires_at);
REVOKE ALL ON telegram_identities, social_auth_flows FROM PUBLIC;

ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_authentication_evidence;
ALTER TABLE sessions ADD CONSTRAINT sessions_authentication_evidence CHECK (
    (authenticated_provider IS NULL AND authenticated_at IS NULL)
    OR (authenticated_provider IS NOT NULL
        AND authenticated_provider IN ('vkid', 'tid', 'email', 'telegram')
        AND authenticated_at IS NOT NULL)
);

COMMIT;
