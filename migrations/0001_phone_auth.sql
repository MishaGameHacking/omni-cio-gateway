BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SEQUENCE IF NOT EXISTS public_profile_id_seq
    AS bigint
    START WITH 1
    INCREMENT BY 1
    MINVALUE 1
    MAXVALUE 999999999
    NO CYCLE
    CACHE 32;

CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    public_id bigint NOT NULL DEFAULT nextval('public_profile_id_seq'),
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'blocked', 'deletion_pending', 'deleted')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    CONSTRAINT users_public_id_unique UNIQUE (public_id),
    CONSTRAINT users_public_id_range CHECK (public_id BETWEEN 1 AND 999999999)
);

CREATE TABLE IF NOT EXISTS phone_identities (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    phone_lookup bytea NOT NULL,
    phone_ciphertext bytea NOT NULL,
    verified_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT phone_identities_lookup_unique UNIQUE (phone_lookup)
);

CREATE TABLE IF NOT EXISTS otp_challenges (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_lookup bytea NOT NULL,
    phone_ciphertext bytea NOT NULL,
    code_digest bytea NOT NULL,
    client_ip_hash bytea NOT NULL,
    attempts_remaining smallint NOT NULL CHECK (attempts_remaining BETWEEN 0 AND 20),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    sent_at timestamptz,
    consumed_at timestamptz,
    provider_message_id text,
    legal_versions jsonb NOT NULL,
    consented_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT otp_expiry_after_creation CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS otp_challenges_phone_created_idx
    ON otp_challenges (phone_lookup, created_at DESC);

CREATE INDEX IF NOT EXISTS otp_challenges_ip_created_idx
    ON otp_challenges (client_ip_hash, created_at DESC);

CREATE INDEX IF NOT EXISTS otp_challenges_expiry_idx
    ON otp_challenges (expires_at)
    WHERE consumed_at IS NULL;

CREATE TABLE IF NOT EXISTS sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_digest bytea NOT NULL,
    client_ip_hash bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    CONSTRAINT sessions_token_digest_unique UNIQUE (token_digest),
    CONSTRAINT sessions_expiry_after_creation CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS sessions_user_active_idx
    ON sessions (user_id, expires_at DESC)
    WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS legal_acceptances (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_type text NOT NULL
        CHECK (document_type IN ('privacy_policy', 'personal_data_consent', 'terms')),
    document_version text NOT NULL,
    accepted_at timestamptz NOT NULL DEFAULT now(),
    client_ip_hash bytea NOT NULL,
    CONSTRAINT legal_acceptance_version_unique
        UNIQUE (user_id, document_type, document_version)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    event_type text NOT NULL,
    request_id text,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_events_user_created_idx
    ON audit_events (user_id, created_at DESC);

COMMIT;
