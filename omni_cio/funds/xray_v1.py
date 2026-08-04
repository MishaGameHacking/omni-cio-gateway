from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from omni_cio.contracts.v1.fund_xray import (
    DirectUnderlyingExposureV1,
    FundBlockerCode,
    FundCompositionMode,
    FundCompositionV1,
    FundConcentrationV1,
    FundExposureDimension,
    FundFreshnessPolicyV1,
    FundHoldingV1,
    FundLookThroughExposureV1,
    FundOverlapKind,
    FundOverlapV1,
    FundProfileV1,
    FundXRayV1,
    OtherFundCompositionV1,
    fund_xray_sha256,
)
from omni_cio.contracts.v1.market import MarketLiquidityV1
from omni_cio.contracts.v1.portfolio import InstrumentType
from omni_cio.contracts.v1.research_evidence import EvidenceUse, ResearchDossierV1
from omni_cio.contracts.v1.universe import MarketUniverseSnapshotV1


class FundXRayError(ValueError):
    """The fund cannot be expanded safely from the supplied evidence."""


_DIMENSION_FIELDS = {
    FundExposureDimension.ASSET_CLASS: "asset_class",
    FundExposureDimension.SECTOR: "sector",
    FundExposureDimension.CURRENCY: "currency",
    FundExposureDimension.ISSUER: "issuer_key",
    FundExposureDimension.GEOGRAPHY: "geography",
}


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise FundXRayError("FUND_XRAY_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _append_unique[T](target: list[T], value: T) -> None:
    if value not in target:
        target.append(value)


def _source_hashes(
    profile: FundProfileV1,
    composition: FundCompositionV1,
) -> tuple[str, ...]:
    hashes: set[str] = set(profile.source_record_sha256s)
    hashes.update(composition.source_record_sha256s)
    for holding in composition.holdings:
        hashes.update(holding.source_record_sha256s)
    for bucket in composition.documented_buckets:
        hashes.update(bucket.source_record_sha256s)
    return tuple(sorted(hashes))


def _provenance_blockers(
    *,
    dossier: ResearchDossierV1,
    profile: FundProfileV1,
    composition: FundCompositionV1,
) -> tuple[FundBlockerCode, ...]:
    records = {row.record_sha256: row for row in dossier.records}
    blockers: list[FundBlockerCode] = []
    for source_hash in _source_hashes(profile, composition):
        record = records.get(source_hash)
        if record is None:
            _append_unique(blockers, FundBlockerCode.SOURCE_PROVENANCE_MISSING)
            continue
        if record.use is not EvidenceUse.DECISION_GRADE:
            _append_unique(blockers, FundBlockerCode.SOURCE_NOT_DECISION_GRADE)
    return tuple(sorted(blockers, key=str))


def _timestamp_stale(
    value: datetime,
    *,
    assessed_at: datetime,
    max_age_seconds: int,
    future_tolerance_seconds: int,
) -> bool:
    age = (assessed_at - value.astimezone(timezone.utc)).total_seconds()
    return age > max_age_seconds or age < -future_tolerance_seconds


def _derive_holding_exposures(
    composition: FundCompositionV1,
) -> tuple[FundLookThroughExposureV1, ...]:
    totals: dict[tuple[FundExposureDimension, str], Decimal] = defaultdict(Decimal)
    for holding in composition.holdings:
        for dimension, field_name in _DIMENSION_FIELDS.items():
            raw = getattr(holding, field_name)
            key = str(raw).strip() if raw is not None else "UNKNOWN"
            if not key:
                key = "UNKNOWN"
            totals[(dimension, key)] += holding.weight

    residual = Decimal("1") - composition.reported_coverage_weight
    if residual < 0:
        residual = Decimal("0")
    for dimension in FundExposureDimension:
        totals[(dimension, "UNKNOWN")] += residual

    return tuple(
        FundLookThroughExposureV1(
            dimension=dimension,
            bucket_key=bucket_key,
            weight=weight,
        )
        for (dimension, bucket_key), weight in sorted(
            totals.items(), key=lambda item: (item[0][0].value, item[0][1])
        )
        if weight > 0
    )


def _derive_documented_exposures(
    composition: FundCompositionV1,
) -> tuple[FundLookThroughExposureV1, ...]:
    totals: dict[tuple[FundExposureDimension, str], Decimal] = defaultdict(Decimal)
    dimensions: set[FundExposureDimension] = set()
    for bucket in composition.documented_buckets:
        dimensions.add(bucket.dimension)
        totals[(bucket.dimension, bucket.bucket_key)] += bucket.weight

    for dimension in dimensions:
        covered = sum(
            (
                weight
                for (candidate_dimension, _), weight in totals.items()
                if candidate_dimension is dimension
            ),
            Decimal("0"),
        )
        residual = Decimal("1") - covered
        if residual > 0:
            totals[(dimension, "UNKNOWN")] += residual

    return tuple(
        FundLookThroughExposureV1(
            dimension=dimension,
            bucket_key=bucket_key,
            weight=weight,
        )
        for (dimension, bucket_key), weight in sorted(
            totals.items(), key=lambda item: (item[0][0].value, item[0][1])
        )
        if weight > 0
    )


def _concentration(
    holdings: tuple[FundHoldingV1, ...],
    coverage: Decimal,
) -> FundConcentrationV1 | None:
    if not holdings:
        return None
    weights = sorted((row.weight for row in holdings), reverse=True)
    return FundConcentrationV1(
        top_1_weight=weights[0],
        top_5_weight=sum(weights[:5], Decimal("0")),
        hhi=sum((weight * weight for weight in weights), Decimal("0")),
        measured_coverage_weight=coverage,
    )


def _direct_overlap(
    holdings: tuple[FundHoldingV1, ...],
    direct: tuple[DirectUnderlyingExposureV1, ...],
) -> FundOverlapV1 | None:
    if not holdings or not direct:
        return None
    direct_keys = {row.holding_key for row in direct if row.portfolio_weight > 0}
    shared = tuple(
        sorted(row.holding_key for row in holdings if row.holding_key in direct_keys)
    )
    if not shared:
        return FundOverlapV1(
            kind=FundOverlapKind.DIRECT_HOLDINGS,
            counterpart_key="portfolio:direct",
            overlap_weight=Decimal("0"),
            shared_holding_keys=(),
        )
    fund_weights = {row.holding_key: row.weight for row in holdings}
    overlap = sum((fund_weights[key] for key in shared), Decimal("0"))
    return FundOverlapV1(
        kind=FundOverlapKind.DIRECT_HOLDINGS,
        counterpart_key="portfolio:direct",
        overlap_weight=overlap,
        shared_holding_keys=shared,
    )


def _fund_overlap(
    holdings: tuple[FundHoldingV1, ...],
    other: OtherFundCompositionV1,
) -> FundOverlapV1:
    left = {row.holding_key: row.weight for row in holdings}
    right = {row.holding_key: row.weight for row in other.holdings}
    shared = tuple(sorted(set(left) & set(right)))
    overlap = sum((min(left[key], right[key]) for key in shared), Decimal("0"))
    return FundOverlapV1(
        kind=FundOverlapKind.OTHER_FUND,
        counterpart_key=other.fund_key,
        overlap_weight=overlap,
        shared_holding_keys=shared,
    )


def _unknown_weight(composition: FundCompositionV1) -> Decimal:
    if composition.mode is FundCompositionMode.UNAVAILABLE:
        return Decimal("1")
    residual = Decimal("1") - composition.reported_coverage_weight
    return max(residual, Decimal("0"))


def build_fund_xray(
    *,
    dossier: ResearchDossierV1,
    universe: MarketUniverseSnapshotV1,
    profile: FundProfileV1,
    composition: FundCompositionV1,
    liquidity: MarketLiquidityV1 | None = None,
    direct_exposures: tuple[DirectUnderlyingExposureV1, ...] = (),
    other_funds: tuple[OtherFundCompositionV1, ...] = (),
    freshness: FundFreshnessPolicyV1 | None = None,
    assessed_at: datetime | None = None,
) -> FundXRayV1:
    """Build deterministic look-through analytics without broker writes."""
    evaluation_time = _aware_utc(assessed_at)
    policy = freshness or FundFreshnessPolicyV1()
    blockers: list[FundBlockerCode] = []

    target = dossier.target
    if target.instrument_type is not InstrumentType.ETF:
        blockers.append(FundBlockerCode.NOT_ETF)
    if not dossier.decision_ready:
        blockers.append(FundBlockerCode.DOSSIER_NOT_READY)
    if profile.instrument.uid != target.instrument_uid:
        blockers.append(FundBlockerCode.DOSSIER_BINDING_MISMATCH)
    if target.asset_uid is not None and profile.asset_uid != target.asset_uid:
        blockers.append(FundBlockerCode.DOSSIER_BINDING_MISMATCH)

    universe_rows = [
        row
        for row in universe.instruments
        if row.identity.uid == target.instrument_uid
    ]
    if (
        not universe.decision_ready
        or len(universe_rows) != 1
        or universe_rows[0].identity.instrument_type is not InstrumentType.ETF
        or universe_rows[0].identity != profile.instrument
    ):
        blockers.append(FundBlockerCode.UNIVERSE_BINDING_MISMATCH)

    blockers.extend(
        _provenance_blockers(
            dossier=dossier,
            profile=profile,
            composition=composition,
        )
    )

    if composition.mode is FundCompositionMode.UNAVAILABLE:
        blockers.append(FundBlockerCode.COMPOSITION_MISSING)
    elif composition.as_of is not None and _timestamp_stale(
        composition.as_of,
        assessed_at=evaluation_time,
        max_age_seconds=policy.composition_max_age_seconds,
        future_tolerance_seconds=policy.future_tolerance_seconds,
    ):
        blockers.append(FundBlockerCode.COMPOSITION_STALE)

    if liquidity is not None:
        if liquidity.instrument_key != f"uid:{target.instrument_uid}":
            blockers.append(FundBlockerCode.LIQUIDITY_IDENTITY_MISMATCH)
        elif _timestamp_stale(
            liquidity.as_of,
            assessed_at=evaluation_time,
            max_age_seconds=policy.liquidity_max_age_seconds,
            future_tolerance_seconds=policy.future_tolerance_seconds,
        ):
            blockers.append(FundBlockerCode.LIQUIDITY_STALE)

    if composition.mode in {
        FundCompositionMode.FULL_HOLDINGS,
        FundCompositionMode.PARTIAL_HOLDINGS,
    }:
        exposures = _derive_holding_exposures(composition)
    elif composition.mode is FundCompositionMode.DOCUMENTED_BUCKETS:
        exposures = _derive_documented_exposures(composition)
    else:
        exposures = ()

    concentration = _concentration(
        composition.holdings,
        composition.reported_coverage_weight,
    )
    overlaps: list[FundOverlapV1] = []
    direct_overlap = _direct_overlap(composition.holdings, direct_exposures)
    if direct_overlap is not None:
        overlaps.append(direct_overlap)
    overlaps.extend(
        _fund_overlap(composition.holdings, other)
        for other in sorted(other_funds, key=lambda row: row.fund_key)
    )

    canonical_blockers = tuple(sorted(set(blockers), key=str))
    values = {
        "schema_version": "1.0",
        "assessed_at": evaluation_time,
        "dossier_sha256": dossier.dossier_sha256,
        "universe_sha256": universe.content_sha256,
        "target": target,
        "profile": profile,
        "composition": composition,
        "liquidity": liquidity,
        "exposures": exposures,
        "concentration": concentration,
        "overlaps": tuple(overlaps),
        "unknown_weight": _unknown_weight(composition),
        "blockers": canonical_blockers,
        "xray_sha256": "0" * 64,
        "decision_ready": not canonical_blockers,
        "trading_methods": False,
    }
    provisional = FundXRayV1.model_construct(**values)
    values["xray_sha256"] = fund_xray_sha256(provisional)
    return FundXRayV1.model_validate(values)
