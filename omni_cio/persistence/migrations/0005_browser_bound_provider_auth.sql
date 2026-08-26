-- WP22A Phase 5: durable browser-bound pre-authentication transactions.
--
-- This central account-plane relation exists before an authenticated tenant can
-- be resolved, so tenant RLS is not applicable. Runtime access is instead
-- limited to the exact SELECT/INSERT/DELETE grant in the hosted role contract.
-- Raw provider state and the raw initiating-browser proof are never persisted.

CREATE TABLE omni_cio_v10.provider_auth_transactions (
    state_sha256 char(64) PRIMARY KEY,
    browser_proof_sha256 char(64) NOT NULL UNIQUE,
    provider text NOT NULL,
    code_verifier text NOT NULL,
    nonce text NOT NULL,
    redirect_uri text NOT NULL,
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    CONSTRAINT provider_auth_state_sha256 CHECK (
        state_sha256 ~ '^[a-f0-9]{64}$'
    ),
    CONSTRAINT provider_auth_browser_proof_sha256 CHECK (
        browser_proof_sha256 ~ '^[a-f0-9]{64}$'
    ),
    CONSTRAINT provider_auth_provider CHECK (
        provider IN ('telegram', 'vk_id')
    ),
    CONSTRAINT provider_auth_code_verifier CHECK (
        code_verifier ~ '^[A-Za-z0-9_-]{43,128}$'
    ),
    CONSTRAINT provider_auth_nonce CHECK (
        nonce ~ '^[A-Za-z0-9_-]{32,512}$'
    ),
    CONSTRAINT provider_auth_redirect_uri CHECK (
        octet_length(redirect_uri) BETWEEN 10 AND 2048 AND
        redirect_uri ~ '^https://'
    ),
    CONSTRAINT provider_auth_lifetime CHECK (
        expires_at > created_at AND
        expires_at <= created_at + interval '15 minutes'
    )
);

CREATE INDEX provider_auth_expiry_idx
    ON omni_cio_v10.provider_auth_transactions (expires_at);
