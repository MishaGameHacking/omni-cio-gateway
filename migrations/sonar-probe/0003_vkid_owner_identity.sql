BEGIN;

CREATE TABLE IF NOT EXISTS vkid_identities (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    vk_user_id text NOT NULL,
    verified_at timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT vkid_identities_user_unique UNIQUE (vk_user_id),
    CONSTRAINT vkid_identities_user_id_nonempty CHECK (char_length(vk_user_id) BETWEEN 1 AND 128)
);

COMMIT;
