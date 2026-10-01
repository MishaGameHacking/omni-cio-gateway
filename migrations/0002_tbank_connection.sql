BEGIN;

CREATE TABLE IF NOT EXISTS tbank_connection (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    environment text NOT NULL
        CHECK (environment IN ('prod', 'sandbox')),
    account_id text NOT NULL
        CHECK (char_length(account_id) BETWEEN 1 AND 128),
    account_name text NOT NULL DEFAULT '',
    token_ciphertext bytea NOT NULL,
    connected_at timestamptz NOT NULL DEFAULT now(),
    verified_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;
