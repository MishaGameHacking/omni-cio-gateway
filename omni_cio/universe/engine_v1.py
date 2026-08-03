from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from typing import Iterable

from omni_cio.contracts.v1.common import (
    Completeness,
    DataIssue,
    DataQuality,
    IssueSeverity,
    QualityMetadata,
)
from omni_cio.contracts.v1.investment_policy import AccountPolicyType
from omni_cio.contracts.v1.universe import (
    MarketUniverseSnapshotV1,
    REQUIRED_UNIVERSE_OPERATIONS,
    UniverseAliasKind,
    UniverseExcludedInstrumentV1,
    UniverseExclusionCode,
    UniverseFetchBatchV1,
    UniverseIdentityConflictV1,
    UniverseInstrumentV1,
    UniverseSourceCountV1,
    UniverseSourceOperation,
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _instrument_payload(row: UniverseInstrumentV1) -> str:
    return _canonical_json(row.model_dump(mode="json"))


def _record_sort_key(row: UniverseInstrumentV1) -> tuple[str, str, str]:
    return (
        row.source_operation.value,
        (row.identity.uid or "").casefold(),
        _instrument_payload(row),
    )


def _deduplicate(
    rows: Iterable[UniverseInstrumentV1],
) -> tuple[tuple[UniverseInstrumentV1, ...], dict[UniverseSourceOperation, int]]:
    unique_by_payload: dict[str, UniverseInstrumentV1] = {}
    duplicates: dict[UniverseSourceOperation, int] = defaultdict(int)
    for row in rows:
        payload = _instrument_payload(row)
        if payload in unique_by_payload:
            duplicates[row.source_operation] += 1
            continue
        unique_by_payload[payload] = row
    unique = tuple(sorted(unique_by_payload.values(), key=_record_sort_key))
    return unique, dict(duplicates)


def _alias_value(row: UniverseInstrumentV1, kind: UniverseAliasKind) -> str | None:
    identity = row.identity
    if kind is UniverseAliasKind.POSITION_UID:
        return identity.position_uid.casefold() if identity.position_uid else None
    if kind is UniverseAliasKind.FIGI:
        return identity.figi.upper() if identity.figi else None
    if kind is UniverseAliasKind.ISIN:
        return identity.isin.upper() if identity.isin else None
    if kind is UniverseAliasKind.TICKER_CLASS_CODE:
        if identity.ticker and identity.class_code:
            return f"{identity.ticker.upper()}::{identity.class_code.upper()}"
        return None
    raise ValueError(f"unsupported alias kind: {kind}")


def _identity_conflicts(
    rows: tuple[UniverseInstrumentV1, ...],
) -> tuple[UniverseIdentityConflictV1, ...]:
    conflicts: list[UniverseIdentityConflictV1] = []

    by_uid: dict[str, list[UniverseInstrumentV1]] = defaultdict(list)
    for row in rows:
        uid = row.identity.uid
        if uid:
            by_uid[uid.casefold()].append(row)
    for uid, group in sorted(by_uid.items()):
        payloads = {_instrument_payload(row) for row in group}
        if len(payloads) > 1:
            conflicts.append(
                UniverseIdentityConflictV1(
                    alias_kind=UniverseAliasKind.UID_PAYLOAD,
                    alias_value=uid,
                    instrument_uids=(uid,),
                    record_count=len(group),
                )
            )

    for kind in (
        UniverseAliasKind.POSITION_UID,
        UniverseAliasKind.FIGI,
        UniverseAliasKind.ISIN,
        UniverseAliasKind.TICKER_CLASS_CODE,
    ):
        groups: dict[str, list[UniverseInstrumentV1]] = defaultdict(list)
        for row in rows:
            alias = _alias_value(row, kind)
            if alias:
                groups[alias].append(row)
        for alias, group in sorted(groups.items()):
            uids = tuple(
                sorted(
                    {
                        row.identity.uid.casefold()
                        for row in group
                        if row.identity.uid
                    }
                )
            )
            if len(uids) > 1:
                conflicts.append(
                    UniverseIdentityConflictV1(
                        alias_kind=kind,
                        alias_value=alias,
                        instrument_uids=uids,
                        record_count=len(group),
                    )
                )

    return tuple(
        sorted(
            conflicts,
            key=lambda row: (
                row.alias_kind.value,
                row.alias_value,
                row.instrument_uids,
            ),
        )
    )


def _exclusion_reasons(
    row: UniverseInstrumentV1,
    *,
    account_type: AccountPolicyType,
    qualified_investor: bool | None,
) -> tuple[UniverseExclusionCode, ...]:
    reasons: list[UniverseExclusionCode] = []
    if not row.api_trade_available:
        reasons.append(UniverseExclusionCode.API_NOT_AVAILABLE)
    if not row.buy_available:
        reasons.append(UniverseExclusionCode.BUY_NOT_AVAILABLE)
    if row.blocked_tca:
        reasons.append(UniverseExclusionCode.BLOCKED_TCA)
    if account_type is AccountPolicyType.IIS and not row.for_iis:
        reasons.append(UniverseExclusionCode.IIS_NOT_ALLOWED)
    if row.for_qual_investor and qualified_investor is not True:
        reasons.append(UniverseExclusionCode.QUALIFICATION_REQUIRED)
    if row.required_tests:
        reasons.append(UniverseExclusionCode.REQUIRED_TESTS_MISSING)
    return tuple(sorted(set(reasons), key=str))


def _quality(
    *,
    batch: UniverseFetchBatchV1,
    conflicts: tuple[UniverseIdentityConflictV1, ...],
    accepted_count: int,
) -> tuple[QualityMetadata, bool]:
    issues: list[DataIssue] = []
    catalog = batch.catalog
    completed = set(catalog.completed_operations)
    missing_operations = tuple(
        operation
        for operation in REQUIRED_UNIVERSE_OPERATIONS
        if operation not in completed
    )

    if catalog.source_errors:
        issues.append(
            DataIssue(
                code="UNIVERSE_SOURCE_ERROR",
                severity=IssueSeverity.ERROR,
                message="One or more broker universe source operations failed.",
                component="market_universe",
            )
        )
    if batch.account_source_error:
        issues.append(
            DataIssue(
                code="ACCOUNT_ELIGIBILITY_ERROR",
                severity=IssueSeverity.ERROR,
                message="Broker account eligibility could not be verified.",
                component="market_universe",
            )
        )
    if missing_operations:
        issues.append(
            DataIssue(
                code="UNIVERSE_SOURCE_INCOMPLETE",
                severity=IssueSeverity.ERROR,
                message="Required broker universe operations are incomplete.",
                component="market_universe",
            )
        )
    if catalog.invalid_rows:
        issues.append(
            DataIssue(
                code="UNIVERSE_INVALID_ROWS",
                severity=IssueSeverity.ERROR,
                message="One or more broker instrument rows failed validation.",
                component="market_universe",
            )
        )
    if conflicts:
        issues.append(
            DataIssue(
                code="UNIVERSE_IDENTITY_CONFLICT",
                severity=IssueSeverity.ERROR,
                message="Instrument identity aliases conflict across broker rows.",
                component="market_universe",
            )
        )
    if batch.account.account_type is AccountPolicyType.UNKNOWN:
        issues.append(
            DataIssue(
                code="ACCOUNT_TYPE_UNKNOWN",
                severity=IssueSeverity.ERROR,
                message="Account type is required for deterministic eligibility.",
                component="market_universe",
            )
        )
    if batch.account.qualified_investor is None:
        issues.append(
            DataIssue(
                code="QUALIFICATION_STATUS_UNKNOWN",
                severity=IssueSeverity.ERROR,
                message="Qualified-investor status is not verified.",
                component="market_universe",
            )
        )
    if accepted_count == 0:
        issues.append(
            DataIssue(
                code="UNIVERSE_EMPTY",
                severity=IssueSeverity.ERROR,
                message="No eligible instruments remain after deterministic gates.",
                component="market_universe",
            )
        )

    ready = not issues
    quality = QualityMetadata(
        quality=DataQuality.VERIFIED if ready else DataQuality.DEGRADED,
        completeness=Completeness.COMPLETE if ready else Completeness.INCOMPLETE,
        issues=tuple(issues),
        warnings=(),
    )
    return quality, ready


def _content_fingerprint(
    *,
    batch: UniverseFetchBatchV1,
    unique_rows: tuple[UniverseInstrumentV1, ...],
    conflicts: tuple[UniverseIdentityConflictV1, ...],
) -> str:
    payload = {
        "source_status": "INSTRUMENT_STATUS_BASE",
        "account": batch.account.model_dump(mode="json"),
        "account_source_error": batch.account_source_error,
        "completed_operations": [
            operation.value for operation in batch.catalog.completed_operations
        ],
        "source_errors": list(batch.catalog.source_errors),
        "invalid_rows": batch.catalog.invalid_rows,
        "instruments": [row.model_dump(mode="json") for row in unique_rows],
        "conflicts": [row.model_dump(mode="json") for row in conflicts],
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def build_market_universe(batch: UniverseFetchBatchV1) -> MarketUniverseSnapshotV1:
    """Build a deterministic, fail-closed candidate universe from broker facts."""

    catalog = batch.catalog
    unique_rows, duplicates_by_source = _deduplicate(catalog.instruments)
    conflicts = _identity_conflicts(unique_rows)

    accepted: list[UniverseInstrumentV1] = []
    excluded: list[UniverseExcludedInstrumentV1] = []
    for row in unique_rows:
        reasons = _exclusion_reasons(
            row,
            account_type=batch.account.account_type,
            qualified_investor=batch.account.qualified_investor,
        )
        if reasons:
            excluded.append(UniverseExcludedInstrumentV1(instrument=row, reasons=reasons))
        else:
            accepted.append(row)

    source_counts: list[UniverseSourceCountV1] = []
    for operation in REQUIRED_UNIVERSE_OPERATIONS:
        received = sum(
            1 for row in catalog.instruments if row.source_operation is operation
        )
        unique = sum(1 for row in unique_rows if row.source_operation is operation)
        accepted_count = sum(
            1 for row in accepted if row.source_operation is operation
        )
        excluded_count = sum(
            1 for row in excluded if row.instrument.source_operation is operation
        )
        source_counts.append(
            UniverseSourceCountV1(
                operation=operation,
                received=received,
                unique=unique,
                accepted=accepted_count,
                excluded=excluded_count,
                duplicates_removed=duplicates_by_source.get(operation, 0),
            )
        )

    quality, ready = _quality(
        batch=batch,
        conflicts=conflicts,
        accepted_count=len(accepted),
    )
    return MarketUniverseSnapshotV1(
        retrieved_at=catalog.retrieved_at,
        account=batch.account,
        completed_operations=catalog.completed_operations,
        instruments=tuple(sorted(accepted, key=_record_sort_key)),
        excluded=tuple(
            sorted(excluded, key=lambda row: _record_sort_key(row.instrument))
        ),
        conflicts=conflicts,
        duplicate_rows_removed=sum(duplicates_by_source.values()),
        source_counts=tuple(source_counts),
        content_sha256=_content_fingerprint(
            batch=batch,
            unique_rows=unique_rows,
            conflicts=conflicts,
        ),
        quality=quality,
        decision_ready=ready,
    )
