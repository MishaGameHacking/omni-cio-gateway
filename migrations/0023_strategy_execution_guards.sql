BEGIN;

CREATE OR REPLACE FUNCTION omnicio_current_strategy_execution_authority(
    owner_id uuid, session_hash bytea, plan jsonb
) RETURNS boolean LANGUAGE sql STABLE AS $execution$
    SELECT EXISTS (
        SELECT 1 FROM users u
        JOIN sessions s ON s.user_id = u.id
        JOIN strategy_drafts d ON d.user_id = u.id
        JOIN tbank_connection b ON b.user_id = u.id
        WHERE u.id = owner_id AND u.status = 'active'
          AND s.token_digest = session_hash AND s.revoked_at IS NULL AND s.expires_at > now()
          AND d.version = (plan->>'strategy_version')::integer
          AND d.document = plan->'document'
          AND b.account_id = plan->>'account_id'
          AND b.environment = plan->>'environment'
          AND b.verified_at = (plan->>'connection_verified_at')::timestamptz
          AND jsonb_typeof(plan->'legal_versions') = 'object'
          AND plan->'legal_versions' <> '{}'::jsonb
          AND NOT EXISTS (
              SELECT 1 FROM jsonb_each_text(plan->'legal_versions') requirement
              WHERE NOT EXISTS (
                  SELECT 1 FROM legal_acceptances acceptance
                  WHERE acceptance.user_id = owner_id
                    AND acceptance.document_type = requirement.key
                    AND acceptance.document_version = requirement.value
              )
          )
    );
$execution$;

CREATE OR REPLACE FUNCTION omnicio_guard_new_strategy_execution()
RETURNS trigger LANGUAGE plpgsql AS $execution$
DECLARE
    plan jsonb;
    digest bytea;
BEGIN
    IF TG_TABLE_NAME = 'portfolio_proposals' THEN
        plan := NEW.payload;
        digest := NEW.created_session_digest;
    ELSIF TG_TABLE_NAME = 'portfolio_execution_runs' THEN
        SELECT payload INTO plan FROM portfolio_proposals
        WHERE id = NEW.proposal_id AND user_id = NEW.user_id;
        digest := NEW.created_session_digest;
    ELSE
        IF NEW.status <> 'submitting' OR OLD.status = NEW.status THEN
            RETURN NEW;
        END IF;
        SELECT p.payload, r.created_session_digest INTO plan, digest
        FROM portfolio_execution_runs r JOIN portfolio_proposals p ON p.id = r.proposal_id
        WHERE r.id = NEW.run_id AND r.user_id = NEW.user_id;
    END IF;
    -- Historical ledgers retain their recovery contract; all new strategy plans are tagged.
    IF plan->>'engine' = 'strategy_execution_1' AND NOT
       omnicio_current_strategy_execution_authority(NEW.user_id, digest, plan) THEN
        RAISE EXCEPTION 'strategy execution authority is no longer current';
    END IF;
    RETURN NEW;
END;
$execution$;

DROP TRIGGER IF EXISTS strategy_proposal_authority ON portfolio_proposals;
CREATE TRIGGER strategy_proposal_authority BEFORE INSERT ON portfolio_proposals
FOR EACH ROW EXECUTE FUNCTION omnicio_guard_new_strategy_execution();
DROP TRIGGER IF EXISTS strategy_run_authority ON portfolio_execution_runs;
CREATE TRIGGER strategy_run_authority BEFORE INSERT ON portfolio_execution_runs
FOR EACH ROW EXECUTE FUNCTION omnicio_guard_new_strategy_execution();
DROP TRIGGER IF EXISTS strategy_submission_authority ON portfolio_execution_legs;
CREATE TRIGGER strategy_submission_authority BEFORE UPDATE OF status ON portfolio_execution_legs
FOR EACH ROW EXECUTE FUNCTION omnicio_guard_new_strategy_execution();

COMMIT;
