BEGIN;

-- Pre-login authentication records retain the same server-only authority as
-- sessions and the accepted provider identity tables. They never grant access
-- to tenant business tables; those continue to use their existing FORCE RLS.
-- Accepted users and legacy sessions survive so a signed-in owner can enroll.
CREATE TABLE IF NOT EXISTS email_identities (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    email text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    password_version integer NOT NULL DEFAULT 1 CHECK (password_version > 0),
    verified_at timestamptz NOT NULL DEFAULT now(),
    password_changed_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT email_identity_address_valid CHECK (
        char_length(email) BETWEEN 3 AND 254
        AND split_part(email, '@', 2) IN ('gmail.com', 'mail.ru', 'xmail.ru')
    ),
    CONSTRAINT email_identity_hash_valid CHECK (
        password_hash LIKE '$argon2id$%' AND char_length(password_hash) <= 512
    )
);

CREATE TABLE IF NOT EXISTS email_auth_challenges (
    id uuid PRIMARY KEY,
    purpose text NOT NULL CHECK (purpose IN ('register', 'enroll', 'reset')),
    email text NOT NULL CHECK (char_length(email) BETWEEN 3 AND 254),
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    enrollment_session_digest bytea,
    password_hash text,
    password_version integer,
    flow_digest bytea NOT NULL CHECK (octet_length(flow_digest) = 32),
    code_digest bytea NOT NULL CHECK (octet_length(code_digest) = 32),
    client_ip_hash bytea NOT NULL CHECK (octet_length(client_ip_hash) = 32),
    legal_versions jsonb NOT NULL DEFAULT '{}'::jsonb,
    attempts_remaining smallint NOT NULL CHECK (attempts_remaining BETWEEN 0 AND 5),
    suppressed boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    resend_at timestamptz NOT NULL,
    delivery_ciphertext bytea,
    delivery_state text NOT NULL CHECK (
        delivery_state IN ('pending', 'sending', 'accepted', 'failed', 'uncertain', 'suppressed')
    ),
    delivery_attempts smallint NOT NULL DEFAULT 0 CHECK (delivery_attempts BETWEEN 0 AND 3),
    next_delivery_at timestamptz NOT NULL DEFAULT now(),
    delivery_started_at timestamptz,
    delivery_code text,
    CONSTRAINT email_challenge_expiry CHECK (expires_at > created_at),
    CONSTRAINT email_challenge_enrollment CHECK (
        (purpose = 'enroll' AND user_id IS NOT NULL
            AND enrollment_session_digest IS NOT NULL
            AND octet_length(enrollment_session_digest) = 32)
        OR (purpose <> 'enroll' AND enrollment_session_digest IS NULL)
    ),
    CONSTRAINT email_challenge_password CHECK (
        (purpose IN ('register', 'enroll') AND password_hash IS NOT NULL
            AND password_hash LIKE '$argon2id$%')
        OR (purpose = 'reset' AND password_hash IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS email_auth_challenges_email_idx
    ON email_auth_challenges (email, purpose, created_at DESC);
CREATE INDEX IF NOT EXISTS email_auth_challenges_delivery_idx
    ON email_auth_challenges (next_delivery_at, created_at)
    WHERE delivery_state = 'pending' AND consumed_at IS NULL;
CREATE INDEX IF NOT EXISTS email_auth_challenges_expiry_idx
    ON email_auth_challenges (expires_at);

-- HMAC identifiers do not expose recipient addresses or network addresses.
CREATE TABLE IF NOT EXISTS email_auth_rate_limits (
    bucket_digest bytea PRIMARY KEY CHECK (octet_length(bucket_digest) = 32),
    window_started_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    attempts integer NOT NULL CHECK (attempts BETWEEN 1 AND 1000000000)
);
CREATE INDEX IF NOT EXISTS email_auth_rate_limits_expiry_idx
    ON email_auth_rate_limits (expires_at);

ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_authentication_evidence;
ALTER TABLE sessions ADD CONSTRAINT sessions_authentication_evidence CHECK (
    (authenticated_provider IS NULL AND authenticated_at IS NULL)
    OR (authenticated_provider IS NOT NULL
        AND authenticated_provider IN ('vkid', 'tid', 'email') AND authenticated_at IS NOT NULL)
);

COMMIT;
