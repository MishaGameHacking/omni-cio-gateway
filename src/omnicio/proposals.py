"""Read-only serialization of saved proposals and their historical decisions."""

from .portfolio_store import PortfolioProposalRecord


def proposal_payload(record: PortfolioProposalRecord) -> dict[str, object]:
    return {
        "id": str(record.id),
        "version": record.version,
        "hash": record.proposal_hash.hex(),
        "source_snapshot_id": str(record.source_snapshot_id),
        "account_id": record.account_id,
        "profile_version": record.profile_version,
        "policy_version": record.policy_version,
        "scenario_kind": record.scenario_kind,
        "target_instrument_uid": record.target_instrument_uid,
        "replaced_instrument_uid": record.replaced_instrument_uid,
        "payload": record.payload,
        "created_at": record.created_at,
        "expires_at": record.expires_at,
        "status": record.status,
        "decision_reason": record.decision_reason,
        "decision_user_reason": record.decision_user_reason,
        "deferred_until": record.deferred_until,
        "decided_at": record.decided_at,
        "execution_enabled": False,
    }
