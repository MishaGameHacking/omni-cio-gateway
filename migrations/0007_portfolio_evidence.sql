BEGIN;

CREATE TABLE IF NOT EXISTS source_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL,
    document_type text NOT NULL,
    subject_uid text NOT NULL,
    provider_key text NOT NULL,
    source_url text NOT NULL,
    published_at timestamptz,
    effective_at timestamptz,
    first_retrieved_at timestamptz NOT NULL,
    content_hash bytea NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT source_documents_provider_nonempty CHECK (
        char_length(provider) BETWEEN 1 AND 64
    ),
    CONSTRAINT source_documents_type_nonempty CHECK (
        char_length(document_type) BETWEEN 1 AND 128
    ),
    CONSTRAINT source_documents_subject_nonempty CHECK (
        char_length(subject_uid) BETWEEN 1 AND 256
    ),
    CONSTRAINT source_documents_key_nonempty CHECK (
        char_length(provider_key) BETWEEN 1 AND 512
    ),
    CONSTRAINT source_documents_url_nonempty CHECK (
        char_length(source_url) BETWEEN 1 AND 2048
    ),
    CONSTRAINT source_documents_hash_size CHECK (octet_length(content_hash) = 32),
    UNIQUE (
        provider,
        document_type,
        subject_uid,
        provider_key,
        content_hash
    )
);

CREATE INDEX IF NOT EXISTS source_documents_subject_idx
    ON source_documents (subject_uid, document_type, effective_at DESC);

CREATE INDEX IF NOT EXISTS source_documents_provider_key_idx
    ON source_documents (provider, document_type, provider_key, first_retrieved_at DESC);

CREATE TABLE IF NOT EXISTS source_retrievals (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_document_id uuid NOT NULL REFERENCES source_documents(id) ON DELETE RESTRICT,
    retrieved_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_document_id, retrieved_at)
);

CREATE INDEX IF NOT EXISTS source_retrievals_document_idx
    ON source_retrievals (source_document_id, retrieved_at DESC);

CREATE TABLE IF NOT EXISTS source_facts (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_document_id uuid NOT NULL REFERENCES source_documents(id) ON DELETE RESTRICT,
    subject_uid text NOT NULL,
    fact_type text NOT NULL,
    fact_key text NOT NULL,
    value_numeric numeric(38, 12),
    value_text text,
    currency text,
    unit text,
    effective_at timestamptz,
    published_at timestamptz,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    semantic_hash bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT source_facts_subject_nonempty CHECK (
        char_length(subject_uid) BETWEEN 1 AND 256
    ),
    CONSTRAINT source_facts_type_nonempty CHECK (
        char_length(fact_type) BETWEEN 1 AND 128
    ),
    CONSTRAINT source_facts_key_nonempty CHECK (
        char_length(fact_key) BETWEEN 1 AND 256
    ),
    CONSTRAINT source_facts_hash_size CHECK (octet_length(semantic_hash) = 32),
    UNIQUE (source_document_id, semantic_hash)
);

CREATE INDEX IF NOT EXISTS source_facts_subject_type_idx
    ON source_facts (subject_uid, fact_type, effective_at DESC);

CREATE TABLE IF NOT EXISTS portfolio_risk_assessments (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    snapshot_id uuid NOT NULL,
    instrument_uid text NOT NULL,
    state text NOT NULL CHECK (
        state IN (
            'data_missing',
            'normal',
            'watch',
            'elevated',
            'critical',
            'confirmed_default'
        )
    ),
    rating_status text NOT NULL CHECK (
        rating_status IN ('data_missing', 'received', 'not_applicable')
    ),
    fundamental_status text NOT NULL CHECK (
        fundamental_status IN ('data_missing', 'received', 'stale', 'not_applicable')
    ),
    source_status text NOT NULL CHECK (
        source_status IN ('received', 'partial', 'unavailable')
    ),
    reasons jsonb NOT NULL,
    evidence jsonb NOT NULL,
    assessed_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (snapshot_id, instrument_uid),
    FOREIGN KEY (snapshot_id, user_id)
        REFERENCES portfolio_snapshots(id, user_id)
        ON DELETE CASCADE,
    CONSTRAINT portfolio_risk_assessments_uid_nonempty CHECK (
        char_length(instrument_uid) BETWEEN 1 AND 128
    )
);

CREATE INDEX IF NOT EXISTS portfolio_risk_assessments_user_assessed_idx
    ON portfolio_risk_assessments (user_id, assessed_at DESC);

ALTER TABLE portfolio_risk_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_risk_assessments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS portfolio_risk_assessments_tenant ON portfolio_risk_assessments;
CREATE POLICY portfolio_risk_assessments_tenant
    ON portfolio_risk_assessments
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

CREATE OR REPLACE FUNCTION omnicio_reject_immutable_evidence_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'immutable evidence rows cannot be updated or deleted';
END;
$$;

DROP TRIGGER IF EXISTS source_documents_immutable ON source_documents;
CREATE TRIGGER source_documents_immutable
BEFORE UPDATE OR DELETE ON source_documents
FOR EACH ROW
EXECUTE FUNCTION omnicio_reject_immutable_evidence_mutation();

DROP TRIGGER IF EXISTS source_retrievals_immutable ON source_retrievals;
CREATE TRIGGER source_retrievals_immutable
BEFORE UPDATE OR DELETE ON source_retrievals
FOR EACH ROW
EXECUTE FUNCTION omnicio_reject_immutable_evidence_mutation();

DROP TRIGGER IF EXISTS source_facts_immutable ON source_facts;
CREATE TRIGGER source_facts_immutable
BEFORE UPDATE OR DELETE ON source_facts
FOR EACH ROW
EXECUTE FUNCTION omnicio_reject_immutable_evidence_mutation();

COMMIT;
