BEGIN;

CREATE TABLE IF NOT EXISTS portfolio_proposals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version integer NOT NULL CHECK (version > 0),
    source_snapshot_id uuid NOT NULL,
    account_id text NOT NULL CHECK (
        char_length(account_id) BETWEEN 1 AND 128
    ),
    profile_version integer NOT NULL CHECK (profile_version > 0),
    policy_version integer NOT NULL CHECK (policy_version > 0),
    scenario_kind text NOT NULL CHECK (
        scenario_kind IN ('deploy_cash', 'replace')
    ),
    target_instrument_uid text,
    replaced_instrument_uid text,
    proposal_hash bytea NOT NULL,
    created_session_digest bytea NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    CONSTRAINT portfolio_proposals_hash_size CHECK (
        octet_length(proposal_hash) = 32
    ),
    CONSTRAINT portfolio_proposals_session_digest_size CHECK (
        octet_length(created_session_digest) = 32
    ),
    CONSTRAINT portfolio_proposals_expiry_after_create CHECK (
        expires_at > created_at
    ),
    CONSTRAINT portfolio_proposals_replace_shape CHECK (
        (
            scenario_kind = 'deploy_cash'
            AND replaced_instrument_uid IS NULL
        )
        OR (
            scenario_kind = 'replace'
            AND replaced_instrument_uid IS NOT NULL
        )
    ),
    CONSTRAINT portfolio_proposals_target_nonempty CHECK (
        target_instrument_uid IS NULL
        OR char_length(target_instrument_uid) BETWEEN 1 AND 128
    ),
    CONSTRAINT portfolio_proposals_replaced_nonempty CHECK (
        replaced_instrument_uid IS NULL
        OR char_length(replaced_instrument_uid) BETWEEN 1 AND 128
    ),
    UNIQUE (id, user_id),
    UNIQUE (user_id, version),
    FOREIGN KEY (source_snapshot_id, user_id)
        REFERENCES portfolio_snapshots(id, user_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS portfolio_proposals_user_created_idx
    ON portfolio_proposals (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS portfolio_proposal_actions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    proposal_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action text NOT NULL CHECK (
        action IN (
            'confirmed',
            'rejected',
            'deferred',
            'superseded',
            'revoked',
            'expired'
        )
    ),
    proposal_version integer NOT NULL CHECK (proposal_version > 0),
    proposal_hash bytea NOT NULL,
    session_digest bytea NOT NULL,
    reason text NOT NULL DEFAULT '',
    user_reason text NOT NULL DEFAULT '',
    deferred_until timestamptz,
    acted_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT portfolio_proposal_actions_hash_size CHECK (
        octet_length(proposal_hash) = 32
    ),
    CONSTRAINT portfolio_proposal_actions_session_digest_size CHECK (
        octet_length(session_digest) = 32
    ),
    CONSTRAINT portfolio_proposal_actions_user_reason_size CHECK (
        char_length(user_reason) <= 500
    ),
    CONSTRAINT portfolio_proposal_actions_reject_reason CHECK (
        action <> 'rejected'
        OR char_length(btrim(user_reason)) BETWEEN 1 AND 500
    ),
    CONSTRAINT portfolio_proposal_actions_deferred_shape CHECK (
        (
            action = 'deferred'
            AND deferred_until IS NOT NULL
        )
        OR (
            action <> 'deferred'
            AND deferred_until IS NULL
        )
    ),
    UNIQUE (proposal_id),
    FOREIGN KEY (proposal_id, user_id)
        REFERENCES portfolio_proposals(id, user_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS portfolio_proposal_actions_user_acted_idx
    ON portfolio_proposal_actions (user_id, acted_at DESC);

ALTER TABLE portfolio_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_proposals FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS portfolio_proposals_tenant ON portfolio_proposals;
CREATE POLICY portfolio_proposals_tenant
    ON portfolio_proposals
    USING (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    );

ALTER TABLE portfolio_proposal_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_proposal_actions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS portfolio_proposal_actions_tenant
    ON portfolio_proposal_actions;
CREATE POLICY portfolio_proposal_actions_tenant
    ON portfolio_proposal_actions
    USING (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    )
    WITH CHECK (
        user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid
    );

CREATE OR REPLACE FUNCTION omnicio_reject_immutable_proposal_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'immutable proposal rows cannot be updated or deleted';
END;
$$;

DROP TRIGGER IF EXISTS portfolio_proposals_immutable ON portfolio_proposals;
CREATE TRIGGER portfolio_proposals_immutable
BEFORE UPDATE OR DELETE ON portfolio_proposals
FOR EACH ROW
EXECUTE FUNCTION omnicio_reject_immutable_proposal_mutation();

DROP TRIGGER IF EXISTS portfolio_proposal_actions_immutable
    ON portfolio_proposal_actions;
CREATE TRIGGER portfolio_proposal_actions_immutable
BEFORE UPDATE OR DELETE ON portfolio_proposal_actions
FOR EACH ROW
EXECUTE FUNCTION omnicio_reject_immutable_proposal_mutation();

COMMIT;
