BEGIN;

-- Explicit, user-controlled context survives reconnects without enabling a model.
CREATE TABLE IF NOT EXISTS assistant_memory (
    user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    id uuid NOT NULL,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    content text NOT NULL CHECK (char_length(content) BETWEEN 1 AND 1000),
    category text NOT NULL CHECK (category IN ('preference', 'context')),
    origin text NOT NULL DEFAULT 'explicit' CHECK (origin = 'explicit'),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, id)
);
CREATE INDEX IF NOT EXISTS assistant_memory_recent
    ON assistant_memory (user_id, updated_at DESC, id);
ALTER TABLE assistant_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE assistant_memory FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS assistant_memory_tenant ON assistant_memory;
CREATE POLICY assistant_memory_tenant ON assistant_memory
    USING (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid)
    WITH CHECK (user_id = NULLIF(current_setting('omnicio.user_id', true), '')::uuid);

-- A disconnected browser can read the durable state before repeating a request.
ALTER TABLE assistant_requests ADD COLUMN IF NOT EXISTS reply_prefix text
    NOT NULL DEFAULT '' CHECK (char_length(reply_prefix) <= 16000);
ALTER TABLE assistant_requests ADD COLUMN IF NOT EXISTS stream_sequence integer
    NOT NULL DEFAULT 0 CHECK (stream_sequence >= 0);
ALTER TABLE assistant_requests ADD COLUMN IF NOT EXISTS source_refs jsonb
    NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(source_refs) = 'array' AND octet_length(source_refs::text) <= 65536);
ALTER TABLE assistant_requests ADD COLUMN IF NOT EXISTS updated_at timestamptz
    NOT NULL DEFAULT now();

-- A completed message retains the same bounded provenance as its stream.
ALTER TABLE assistant_messages DROP CONSTRAINT IF EXISTS assistant_messages_sources_check;
ALTER TABLE assistant_messages DROP CONSTRAINT IF EXISTS assistant_messages_source_refs_size;
ALTER TABLE assistant_messages ADD CONSTRAINT assistant_messages_source_refs_size
    CHECK (jsonb_typeof(sources) = 'array' AND octet_length(sources::text) <= 65536);

COMMIT;
