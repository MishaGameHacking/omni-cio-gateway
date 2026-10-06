BEGIN;

-- One replaceable working copy per tenant; confirmed profile/policy history is separate.
CREATE TABLE IF NOT EXISTS strategy_drafts (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    version integer NOT NULL CHECK (version > 0),
    document jsonb NOT NULL CHECK (jsonb_typeof(document) = 'object'),
    custom_document jsonb CHECK (custom_document IS NULL OR jsonb_typeof(custom_document) = 'object'),
    fingerprint text NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (octet_length(document::text) <= 32768),
    CHECK (custom_document IS NULL OR octet_length(custom_document::text) <= 32768)
);

ALTER TABLE strategy_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_drafts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS strategy_drafts_tenant ON strategy_drafts;
CREATE POLICY strategy_drafts_tenant ON strategy_drafts
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

COMMIT;
