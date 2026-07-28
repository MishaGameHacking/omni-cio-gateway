from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.analytics import AdvancedPortfolioAnalyticsV1
from omni_cio.contracts.v1.common import (
    Completeness,
    ContractMetadata,
    DataQuality,
    IssueSeverity,
    QualityMetadata,
    SourceReference,
)
from omni_cio.contracts.v1.decision import (
    DecisionAction,
    DecisionBlocker,
    DecisionConfidence,
    DecisionEvidenceKind,
    DecisionEvidenceV1,
    DecisionOptionKind,
    DecisionOptionStatus,
    DecisionOptionV1,
    DecisionSetV1,
    InstrumentMarketReadinessV1,
)
from omni_cio.contracts.v1.news import (
    NewsDisposition,
    SanitizedNewsDocumentV1,
)
from omni_cio.contracts.v1.risk import (
    RiskCheckStatus,
    RiskOverallStatus,
    RiskPolicyEvaluationV1,
)


class DecisionEngineError(ValueError):
    """The supplied evidence cannot form a deterministic decision set."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise DecisionEngineError("DECISION_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _append_unique(target: list[DecisionBlocker], value: DecisionBlocker) -> None:
    if value not in target:
        target.append(value)


def _portfolio_ready(analytics: AdvancedPortfolioAnalyticsV1) -> bool:
    quality = analytics.metadata.quality
    blocking_issue = any(
        issue.severity in (IssueSeverity.WARNING, IssueSeverity.ERROR)
        for issue in quality.issues
    )
    return (
        analytics.decision_ready
        and analytics.no_cross_currency_aggregation
        and quality.quality == DataQuality.VERIFIED
        and quality.completeness == Completeness.COMPLETE
        and not blocking_issue
    )


def _risk_ready(evaluation: RiskPolicyEvaluationV1) -> bool:
    quality = evaluation.metadata.quality
    blocking_issue = any(
        issue.severity in (IssueSeverity.WARNING, IssueSeverity.ERROR)
        for issue in quality.issues
    )
    return (
        evaluation.decision_ready
        and evaluation.no_cross_currency_aggregation
        and evaluation.overall_status in (
            RiskOverallStatus.PASS,
            RiskOverallStatus.WARNING,
        )
        and quality.quality == DataQuality.VERIFIED
        and quality.completeness == Completeness.COMPLETE
        and not blocking_issue
    )


def _portfolio_instrument_keys(
    analytics: AdvancedPortfolioAnalyticsV1,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                position.stable_key
                for currency in analytics.by_currency
                for position in currency.positions
            }
        )
    )


def _market_coverage(
    *,
    required_keys: tuple[str, ...],
    market_states: tuple[InstrumentMarketReadinessV1, ...],
    blockers: list[DecisionBlocker],
) -> tuple[int, dict[str, InstrumentMarketReadinessV1]]:
    by_key: dict[str, InstrumentMarketReadinessV1] = {}
    for market_state in market_states:
        if market_state.instrument_key in by_key:
            raise DecisionEngineError("DUPLICATE_MARKET_READINESS_INSTRUMENT")
        by_key[market_state.instrument_key] = market_state

    missing = set(required_keys) - set(by_key)
    if missing:
        _append_unique(blockers, DecisionBlocker.MARKET_COVERAGE_INCOMPLETE)

    coverage_count = 0
    for instrument_key in required_keys:
        row = by_key.get(instrument_key)
        if row is None:
            continue
        if row.assessment.decision_ready:
            coverage_count += 1
        else:
            _append_unique(blockers, DecisionBlocker.MARKET_NOT_READY)
    return coverage_count, by_key


def _news_state(
    documents: tuple[SanitizedNewsDocumentV1, ...],
    blockers: list[DecisionBlocker],
) -> tuple[int, int, int]:
    accepted = tuple(
        document
        for document in documents
        if document.disposition == NewsDisposition.ACCEPTED
    )
    context_count = sum(
        document.disposition == NewsDisposition.CONTEXT_ONLY
        for document in documents
    )
    rejected_count = sum(
        document.disposition == NewsDisposition.REJECTED
        for document in documents
    )

    if documents and not accepted:
        _append_unique(blockers, DecisionBlocker.NEWS_EVIDENCE_UNUSABLE)

    fingerprints_by_cluster: dict[tuple[str, str], set[str]] = defaultdict(set)
    for document in accepted:
        if document.instrument_key is None:
            raise DecisionEngineError("ACCEPTED_NEWS_WITHOUT_INSTRUMENT")
        cluster_key = (document.instrument_key, document.event_cluster_id)
        fingerprints_by_cluster[cluster_key].add(document.content_fingerprint)
    if any(
        len(fingerprints) > 1
        for fingerprints in fingerprints_by_cluster.values()
    ):
        _append_unique(blockers, DecisionBlocker.NEWS_CONTRADICTION)

    return len(accepted), context_count, rejected_count


def _blocker_statement(blocker: DecisionBlocker) -> str:
    statements = {
        DecisionBlocker.PORTFOLIO_NOT_READY: (
            "Portfolio analytics is not verified and complete."
        ),
        DecisionBlocker.RISK_NOT_READY: (
            "Risk-policy evaluation contains a blocking breach or unknown input."
        ),
        DecisionBlocker.MARKET_NOT_READY: (
            "At least one required market assessment is stale, missing or untrusted."
        ),
        DecisionBlocker.MARKET_COVERAGE_INCOMPLETE: (
            "Market readiness is absent for at least one portfolio instrument."
        ),
        DecisionBlocker.NEWS_EVIDENCE_UNUSABLE: (
            "Provided news contains no accepted resolved fact."
        ),
        DecisionBlocker.NEWS_CONTRADICTION: (
            "Accepted news records disagree within the same event cluster."
        ),
        DecisionBlocker.REBALANCING_ENGINE_NOT_AVAILABLE: (
            "Exact threshold rebalancing and sizing are deferred to PR-13."
        ),
    }
    return statements[blocker]


def _build_evidence(
    *,
    analytics: AdvancedPortfolioAnalyticsV1,
    risk_evaluation: RiskPolicyEvaluationV1,
    required_market_count: int,
    market_coverage_count: int,
    accepted_news_count: int,
    context_news_count: int,
    rejected_news_count: int,
    blockers: tuple[DecisionBlocker, ...],
) -> tuple[DecisionEvidenceV1, ...]:
    position_count = sum(
        currency.position_count for currency in analytics.by_currency
    )
    evidence: list[DecisionEvidenceV1] = [
        DecisionEvidenceV1(
            evidence_id="source.portfolio",
            kind=DecisionEvidenceKind.FACT,
            statement=(
                f"Verified analytics covers {position_count} positions across "
                f"{len(analytics.by_currency)} currencies."
            ),
            source_schema=analytics.metadata.schema_name,
            source_id=analytics.metadata.schema_version,
            observed_value=Decimal(position_count),
        ),
        DecisionEvidenceV1(
            evidence_id="source.risk",
            kind=DecisionEvidenceKind.FACT,
            statement=(
                f"Risk policy status is {risk_evaluation.overall_status.value}; "
                f"warnings={risk_evaluation.warning_count}, "
                f"breaches={risk_evaluation.breach_count}, "
                f"unknown={risk_evaluation.unknown_count}."
            ),
            source_schema=risk_evaluation.metadata.schema_name,
            source_id=risk_evaluation.policy.policy_version,
            observed_value=Decimal(risk_evaluation.warning_count),
        ),
        DecisionEvidenceV1(
            evidence_id="source.market_coverage",
            kind=DecisionEvidenceKind.CALCULATION,
            statement=(
                f"Decision-ready market coverage is {market_coverage_count} of "
                f"{required_market_count} required instruments."
            ),
            source_schema="market_readiness_assessment",
            observed_value=Decimal(market_coverage_count),
            limit_value=Decimal(required_market_count),
        ),
        DecisionEvidenceV1(
            evidence_id="source.news",
            kind=DecisionEvidenceKind.FACT,
            statement=(
                f"News evidence: accepted={accepted_news_count}, "
                f"context_only={context_news_count}, rejected={rejected_news_count}."
            ),
            source_schema="sanitized_news_document",
            observed_value=Decimal(accepted_news_count),
        ),
    ]

    for check in risk_evaluation.checks:
        if check.status != RiskCheckStatus.WARNING:
            continue
        evidence.append(
            DecisionEvidenceV1(
                evidence_id=f"risk.{check.check_id}",
                kind=DecisionEvidenceKind.WARNING,
                statement=check.message,
                source_schema=risk_evaluation.metadata.schema_name,
                source_id=check.check_id,
                observed_value=check.observed_value,
                limit_value=check.limit_value,
                currency=check.currency,
                instrument_key=check.subject,
            )
        )

    for blocker in blockers:
        evidence.append(
            DecisionEvidenceV1(
                evidence_id=f"missing.{blocker.value}",
                kind=DecisionEvidenceKind.MISSING_DATA,
                statement=_blocker_statement(blocker),
                source_schema="decision_engine",
                source_id=blocker.value,
            )
        )
    return tuple(evidence)


def _option_evidence_ids(
    evidence: tuple[DecisionEvidenceV1, ...],
) -> tuple[str, ...]:
    return tuple(row.evidence_id for row in evidence)


def _build_options(
    *,
    blockers: tuple[DecisionBlocker, ...],
    warning_count: int,
    confidence: DecisionConfidence,
    evidence_ids: tuple[str, ...],
) -> tuple[DecisionOptionV1, ...]:
    if blockers:
        no_action = DecisionOptionV1(
            option_id="option.no_action",
            kind=DecisionOptionKind.NO_ACTION,
            status=DecisionOptionStatus.PREFERRED,
            action=DecisionAction.WAIT_FOR_DATA,
            title="Do nothing and wait for reliable data",
            rationale=(
                "A blocking data or risk gate is open. Any portfolio change would "
                "rely on incomplete or contradictory evidence."
            ),
            confidence=DecisionConfidence.LOW,
            evidence_ids=evidence_ids,
            review_conditions=tuple(
                _blocker_statement(blocker) for blocker in blockers
            ),
        )
        limited = DecisionOptionV1(
            option_id="option.limited_change",
            kind=DecisionOptionKind.LIMITED_CHANGE,
            status=DecisionOptionStatus.BLOCKED,
            action=DecisionAction.REVIEW_LIMITED_CHANGE,
            title="Review a limited change",
            rationale="Limited changes are blocked until every global gate closes.",
            confidence=DecisionConfidence.LOW,
            evidence_ids=evidence_ids,
            blockers=blockers,
        )
        strategic_blockers = tuple(
            dict.fromkeys(
                (*blockers, DecisionBlocker.REBALANCING_ENGINE_NOT_AVAILABLE)
            )
        )
        strategic = DecisionOptionV1(
            option_id="option.strategic_rebalance",
            kind=DecisionOptionKind.STRATEGIC_REBALANCE,
            status=DecisionOptionStatus.BLOCKED,
            action=DecisionAction.REVIEW_STRATEGIC_REBALANCE,
            title="Review a strategic rebalance",
            rationale=(
                "Strategic rebalancing is blocked by open gates and has no sizing "
                "engine before PR-13."
            ),
            confidence=DecisionConfidence.LOW,
            evidence_ids=evidence_ids,
            blockers=strategic_blockers,
        )
        return no_action, limited, strategic

    if warning_count > 0:
        no_action_status = DecisionOptionStatus.AVAILABLE
        limited_status = DecisionOptionStatus.PREFERRED
        no_action_rationale = (
            "Holding remains a valid alternative, but verified risk warnings justify "
            "reviewing a bounded change."
        )
        limited_rationale = (
            "Verified non-blocking risk warnings support reviewing a limited change. "
            "PR-12 does not choose a specific trade size."
        )
    else:
        no_action_status = DecisionOptionStatus.PREFERRED
        limited_status = DecisionOptionStatus.AVAILABLE
        no_action_rationale = (
            "All gates pass and no verified risk warning requires a portfolio change."
        )
        limited_rationale = (
            "A limited change may be reviewed, but current verified evidence does not "
            "make it preferable to holding."
        )

    no_action = DecisionOptionV1(
        option_id="option.no_action",
        kind=DecisionOptionKind.NO_ACTION,
        status=no_action_status,
        action=DecisionAction.HOLD,
        title="Keep the current structure",
        rationale=no_action_rationale,
        confidence=confidence,
        evidence_ids=evidence_ids,
        review_conditions=(
            "Re-run the decision when portfolio, risk, market or event data changes.",
        ),
    )
    limited = DecisionOptionV1(
        option_id="option.limited_change",
        kind=DecisionOptionKind.LIMITED_CHANGE,
        status=limited_status,
        action=DecisionAction.REVIEW_LIMITED_CHANGE,
        title="Review a limited portfolio change",
        rationale=limited_rationale,
        confidence=confidence,
        evidence_ids=evidence_ids,
        review_conditions=(
            "Sizing, lot constraints, commissions and post-trade weights require PR-13/14.",
        ),
    )
    strategic = DecisionOptionV1(
        option_id="option.strategic_rebalance",
        kind=DecisionOptionKind.STRATEGIC_REBALANCE,
        status=DecisionOptionStatus.REVIEW_ONLY,
        action=DecisionAction.REVIEW_STRATEGIC_REBALANCE,
        title="Review a larger strategic rebalance",
        rationale=(
            "The option is considered for completeness, but exact target ranges and "
            "trade sizing are deferred to PR-13."
        ),
        confidence=confidence,
        evidence_ids=evidence_ids,
        review_conditions=(
            "Do not convert this review option into orders before threshold rebalancing exists.",
        ),
    )
    return no_action, limited, strategic


def build_decision_set(
    analytics: AdvancedPortfolioAnalyticsV1,
    risk_evaluation: RiskPolicyEvaluationV1,
    *,
    market_states: Iterable[InstrumentMarketReadinessV1] = (),
    news_documents: Iterable[SanitizedNewsDocumentV1] = (),
    decided_at: datetime | None = None,
) -> DecisionSetV1:
    """Build three analytical alternatives and abstain whenever a gate is open."""
    evaluation_time = _aware_utc(decided_at)
    markets = tuple(market_states)
    news = tuple(news_documents)
    blockers: list[DecisionBlocker] = []

    if not _portfolio_ready(analytics):
        _append_unique(blockers, DecisionBlocker.PORTFOLIO_NOT_READY)
    if not _risk_ready(risk_evaluation):
        _append_unique(blockers, DecisionBlocker.RISK_NOT_READY)

    required_keys = _portfolio_instrument_keys(analytics)
    market_coverage_count, _ = _market_coverage(
        required_keys=required_keys,
        market_states=markets,
        blockers=blockers,
    )
    accepted_news_count, context_news_count, rejected_news_count = _news_state(
        news,
        blockers,
    )

    blocker_tuple = tuple(blockers)
    evidence = _build_evidence(
        analytics=analytics,
        risk_evaluation=risk_evaluation,
        required_market_count=len(required_keys),
        market_coverage_count=market_coverage_count,
        accepted_news_count=accepted_news_count,
        context_news_count=context_news_count,
        rejected_news_count=rejected_news_count,
        blockers=blocker_tuple,
    )

    if blocker_tuple:
        confidence = DecisionConfidence.LOW
    elif risk_evaluation.warning_count > 0 or accepted_news_count == 0:
        confidence = DecisionConfidence.MEDIUM
    else:
        confidence = DecisionConfidence.HIGH

    options = _build_options(
        blockers=blocker_tuple,
        warning_count=risk_evaluation.warning_count,
        confidence=confidence,
        evidence_ids=_option_evidence_ids(evidence),
    )
    preferred = next(
        option
        for option in options
        if option.status == DecisionOptionStatus.PREFERRED
    )

    metadata = ContractMetadata(
        schema_name="decision_set",
        retrieved_at=evaluation_time,
        account=analytics.metadata.account,
        provenance=(
            *analytics.metadata.provenance,
            *risk_evaluation.metadata.provenance,
            SourceReference(
                provider="omni-cio",
                operation="build_decision_set",
                retrieved_at=evaluation_time,
                source_id="1.0",
            ),
        ),
        quality=QualityMetadata(
            quality=(
                DataQuality.PARTIAL if blocker_tuple else DataQuality.VERIFIED
            ),
            completeness=(
                Completeness.PARTIAL
                if blocker_tuple
                else Completeness.COMPLETE
            ),
            warnings=(
                "Decision options are analytical only; no order parameters are produced.",
            ),
        ),
    )
    return DecisionSetV1(
        metadata=metadata,
        evidence=evidence,
        options=options,
        preferred_option_id=preferred.option_id,
        abstain=bool(blocker_tuple),
        recommendation_ready=not blocker_tuple,
        confidence=confidence,
        global_blockers=blocker_tuple,
        accepted_news_count=accepted_news_count,
        context_news_count=context_news_count,
        rejected_news_count=rejected_news_count,
        required_market_count=len(required_keys),
        market_coverage_count=market_coverage_count,
        trading_methods=False,
    )
