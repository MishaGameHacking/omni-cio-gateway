BEGIN;

-- R7 live authority is intentionally bound to the authenticated session that
-- created the mandate. Replacing these trigger functions preserves the
-- immutable ledger schema while tightening the existing insert/submission
-- guards for all future live mutations.

CREATE OR REPLACE FUNCTION omnicio_validate_execution_run_source()
RETURNS trigger
LANGUAGE plpgsql
AS $omnicio$
BEGIN
    IF TG_OP = 'UPDATE' AND (
        NEW.user_id,
        NEW.proposal_id,
        NEW.confirmed_action_id,
        NEW.proposal_version,
        NEW.proposal_hash,
        NEW.account_id,
        NEW.mode,
        NEW.provider_environment,
        NEW.live_mandate_id,
        NEW.created_session_digest
    ) IS DISTINCT FROM (
        OLD.user_id,
        OLD.proposal_id,
        OLD.confirmed_action_id,
        OLD.proposal_version,
        OLD.proposal_hash,
        OLD.account_id,
        OLD.mode,
        OLD.provider_environment,
        OLD.live_mandate_id,
        OLD.created_session_digest
    ) THEN
        RAISE EXCEPTION 'execution source fields are immutable';
    END IF;

    IF TG_OP = 'INSERT' AND NOT EXISTS (
        SELECT 1
        FROM portfolio_proposals AS p
        JOIN portfolio_proposal_actions AS a
          ON a.proposal_id = p.id
         AND a.user_id = p.user_id
        WHERE p.id = NEW.proposal_id
          AND p.user_id = NEW.user_id
          AND p.version = NEW.proposal_version
          AND p.proposal_hash = NEW.proposal_hash
          AND p.account_id = NEW.account_id
          AND p.expires_at > now()
          AND (p.source_snapshot_id, p.account_id) = (
              SELECT s.id, s.account_id
              FROM portfolio_snapshots AS s
              WHERE s.user_id = NEW.user_id
              ORDER BY s.captured_at DESC, s.created_at DESC
              LIMIT 1
          )
          AND p.profile_version = (
              SELECT ip.version
              FROM investment_profile_versions AS ip
              WHERE ip.user_id = NEW.user_id
              ORDER BY ip.version DESC
              LIMIT 1
          )
          AND p.policy_version = (
              SELECT bp.version
              FROM balancing_policy_versions AS bp
              WHERE bp.user_id = NEW.user_id
              ORDER BY bp.version DESC
              LIMIT 1
          )
          AND a.id = NEW.confirmed_action_id
          AND a.action = 'confirmed'
          AND a.proposal_version = NEW.proposal_version
          AND a.proposal_hash = NEW.proposal_hash
    ) THEN
        RAISE EXCEPTION 'execution source is not an exact confirmed proposal';
    END IF;

    IF TG_OP = 'INSERT'
       AND NEW.mode = 'live'
       AND NOT EXISTS (
           SELECT 1
           FROM portfolio_live_execution_mandates AS m
           WHERE m.id = NEW.live_mandate_id
             AND m.user_id = NEW.user_id
             AND m.account_id = NEW.account_id
             AND m.created_session_digest = NEW.created_session_digest
             AND m.revoked_at IS NULL
             AND m.expires_at > now()
       ) THEN
        RAISE EXCEPTION 'live execution requires an active exact-account same-session mandate';
    END IF;

    RETURN NEW;
END;
$omnicio$;


CREATE OR REPLACE FUNCTION omnicio_validate_live_submission_authority()
RETURNS trigger
LANGUAGE plpgsql
AS $omnicio$
BEGIN
    IF NEW.status = 'submitting'
       AND OLD.status IS DISTINCT FROM NEW.status
       AND EXISTS (
           SELECT 1
           FROM portfolio_execution_runs AS r
           WHERE r.id = NEW.run_id
             AND r.user_id = NEW.user_id
             AND r.mode = 'live'
       ) THEN
        PERFORM 1
        FROM portfolio_execution_runs AS r
        JOIN portfolio_live_execution_mandates AS m
          ON m.id = r.live_mandate_id
         AND m.user_id = r.user_id
         AND m.account_id = r.account_id
         AND m.created_session_digest = r.created_session_digest
        WHERE r.id = NEW.run_id
          AND r.user_id = NEW.user_id
          AND r.mode = 'live'
          AND m.revoked_at IS NULL
          AND m.expires_at > now()
        FOR SHARE OF m;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'live execution mandate is inactive or session-mismatched before submission';
        END IF;
    END IF;
    RETURN NEW;
END;
$omnicio$;

COMMIT;
