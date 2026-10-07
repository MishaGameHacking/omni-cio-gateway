BEGIN;

-- A second verified identity provider; accepted VK ID users and sessions survive.
CREATE TABLE IF NOT EXISTS tid_identities (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    tid_subject text NOT NULL UNIQUE,
    verified_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (char_length(tid_subject) BETWEEN 1 AND 128)
);

-- The pre-login identity resolver deliberately has the same restricted server
-- authority as vkid_identities. No identity table has a browser-facing read API.
CREATE TABLE IF NOT EXISTS oauth_flow_claims (
    state_digest bytea PRIMARY KEY,
    provider text NOT NULL CHECK (provider IN ('vkid', 'tid')),
    expires_at timestamptz NOT NULL,
    CHECK (octet_length(state_digest) = 32)
);
CREATE INDEX IF NOT EXISTS oauth_flow_claims_expiry_idx ON oauth_flow_claims (expires_at);

COMMIT;
