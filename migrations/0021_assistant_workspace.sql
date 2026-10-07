BEGIN;

CREATE TABLE IF NOT EXISTS assistant_connections (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    active boolean NOT NULL DEFAULT true,
    provider text NOT NULL CHECK (provider IN ('ollama', 'openai_compatible')),
    base_url text NOT NULL CHECK (char_length(base_url) <= 1000),
    model text NOT NULL CHECK (char_length(model) <= 200),
    key_ciphertext bytea,
    health_status text NOT NULL DEFAULT 'unchecked'
        CHECK (health_status IN ('unchecked', 'healthy', 'unavailable', 'model_missing')),
    checked_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (NOT active OR (char_length(base_url) > 0 AND char_length(model) > 0))
);
CREATE TABLE IF NOT EXISTS assistant_conversations (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    title text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 120),
    version integer NOT NULL DEFAULT 0 CHECK (version >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, id)
);
CREATE TABLE IF NOT EXISTS assistant_requests (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    id uuid NOT NULL,
    conversation_id uuid,
    input_hash text NOT NULL CHECK (input_hash ~ '^[0-9a-f]{64}$'),
    connection_version integer NOT NULL CHECK (connection_version >= 0),
    conversation_version integer NOT NULL CHECK (conversation_version > 0),
    status text NOT NULL CHECK (status IN ('running', 'completed', 'uncertain', 'cancelled')),
    context_used boolean NOT NULL,
    model text NOT NULL CHECK (char_length(model) <= 200),
    input_tokens integer CHECK (input_tokens IS NULL OR input_tokens >= 0),
    output_tokens integer CHECK (output_tokens IS NULL OR output_tokens >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    PRIMARY KEY (user_id, id),
    FOREIGN KEY (user_id, conversation_id) REFERENCES assistant_conversations(user_id, id)
        ON DELETE SET NULL (conversation_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS assistant_requests_active_idx
    ON assistant_requests (user_id) WHERE status = 'running';
CREATE INDEX IF NOT EXISTS assistant_requests_quota_idx ON assistant_requests (user_id, created_at);
CREATE TABLE IF NOT EXISTS assistant_messages (
    user_id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    position integer NOT NULL CHECK (position > 0),
    request_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('user', 'assistant')),
    content text NOT NULL CHECK (char_length(content) BETWEEN 1 AND 16000),
    sources jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(sources) = 'array' AND octet_length(sources::text) <= 8192),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, conversation_id, position),
    UNIQUE (user_id, request_id, role),
    FOREIGN KEY (user_id, conversation_id) REFERENCES assistant_conversations(user_id, id)
        ON DELETE CASCADE,
    FOREIGN KEY (user_id, request_id) REFERENCES assistant_requests(user_id, id) ON DELETE CASCADE
);

DO $assistant$
DECLARE relation_name text;
BEGIN
    FOREACH relation_name IN ARRAY ARRAY[
        'assistant_connections', 'assistant_conversations', 'assistant_requests', 'assistant_messages'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', relation_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', relation_name);
        EXECUTE format('DROP POLICY IF EXISTS assistant_tenant ON %I', relation_name);
        EXECUTE format(
            'CREATE POLICY assistant_tenant ON %I USING '
            '(user_id = NULLIF(current_setting(''omnicio.user_id'', true), '''')::uuid) '
            'WITH CHECK (user_id = NULLIF(current_setting(''omnicio.user_id'', true), '''')::uuid)',
            relation_name
        );
    END LOOP;
END $assistant$;

COMMIT;
