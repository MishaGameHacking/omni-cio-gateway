-- Durable per-owner cooldown; existing FORCE RLS and deletion cascade apply.
-- The matching session advisory lock is held only by the read-only assessment.
ALTER TABLE strategy_drafts
    ADD COLUMN IF NOT EXISTS next_assessment_at timestamptz NOT NULL DEFAULT '-infinity';
