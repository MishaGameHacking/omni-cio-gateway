from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
from typing import Any

from t_tech.invest import InstrumentIdType

from omni_cio.adapters.tinvest_market_v1 import TInvestMarketReadAdapter
from omni_cio.adapters.tinvest_read_v1 import (
    ACCESS_LEVEL_NAMES,
    ACCOUNT_STATUS_NAMES,
    AccountBindingError,
    BrokerAccountBindingV1,
    BrokerDataError,
    TInvestReadAdapter,
    TInvestReadAdapterError,
    _accounts,
    _binding_for_account,
    _enum_name,
    _field,
    _message_to_dict,
)
from omni_cio.contracts.v1.portfolio import InstrumentIdentity, InstrumentType


_READ_ONLY = "ACCOUNT_ACCESS_LEVEL_READ_ONLY"
_NO_ACCESS = "ACCOUNT_ACCESS_LEVEL_NO_ACCESS"
_OPEN = "ACCOUNT_STATUS_OPEN"


@dataclass(frozen=True, slots=True)
class TInvestInstrumentClassificationV1:
    instrument_uid: str
    issuer: str | None
    sector: str | None
    source: str
    retrieved_at: datetime
    state: str


def _readable_open_accounts(
    response: Any,
) -> tuple[tuple[str, BrokerAccountBindingV1], ...]:
    """Return verified READ-only open accounts without exposing raw provider IDs."""
    bindings: list[tuple[str, BrokerAccountBindingV1]] = []
    seen_raw_ids: set[str] = set()

    for account in _accounts(response):
        status = _enum_name(_field(account, "status"), ACCOUNT_STATUS_NAMES)
        access_level = _enum_name(
            _field(account, "access_level"),
            ACCESS_LEVEL_NAMES,
        )
        if access_level == _NO_ACCESS:
            continue
        if access_level != _READ_ONLY:
            raise AccountBindingError("BROKER_READ_CREDENTIAL_NOT_READ_ONLY")
        if status != _OPEN:
            continue

        raw_account_id, binding = _binding_for_account(account)
        if raw_account_id in seen_raw_ids:
            raise AccountBindingError("DUPLICATE_ACCESSIBLE_ACCOUNT_BINDING")
        seen_raw_ids.add(raw_account_id)
        bindings.append((raw_account_id, binding))

    if not bindings:
        raise AccountBindingError("NO_ACCESSIBLE_OPEN_ACCOUNT")

    bindings.sort(key=lambda pair: pair[1].broker_account_id)
    return tuple(bindings)


def discover_read_account_bindings(
    client_factory: Callable[[], Any],
) -> tuple[BrokerAccountBindingV1, ...]:
    """Discover all READ-only broker accounts as masked, non-secret bindings.

    The raw broker account identifiers are intentionally retained only inside the adapter
    boundary. The Web/API layer receives canonical broker-account IDs, fingerprints and
    masked labels, never the provider account ID itself.
    """
    with client_factory() as client:
        response = client.users.get_accounts()
        return tuple(binding for _, binding in _readable_open_accounts(response))


class TInvestConnectionReadAdapter(TInvestReadAdapter):
    """Connection-scoped WP15 adapter for one verified broker account.

    A READ credential may expose one or many T-Invest accounts. This adapter binds the
    operation to exactly one preselected account fingerprint owned by the authenticated
    tenant/BrokerConnection. Broader token authority, absent identity and duplicate
    bindings fail closed before any portfolio/operations read is made.
    """

    def _bind_account(
        self,
        client: Any,
    ) -> tuple[str, BrokerAccountBindingV1]:
        response = self._call_read("GET_ACCOUNTS", client.users.get_accounts)
        matches: list[tuple[str, BrokerAccountBindingV1]] = []
        for raw_account_id, binding in _readable_open_accounts(response):
            if hmac.compare_digest(
                binding.account_fingerprint_sha256,
                self._expected_account_fingerprint,
            ):
                matches.append((raw_account_id, binding))

        if not matches:
            raise AccountBindingError("EXPECTED_ACCOUNT_NOT_ACCESSIBLE")
        if len(matches) != 1:
            raise AccountBindingError("DUPLICATE_EXPECTED_ACCOUNT_BINDING")
        return matches[0]


class TInvestConnectionMarketReadAdapter(
    TInvestMarketReadAdapter,
    TInvestConnectionReadAdapter,
):
    """Market companion using the same exact connection-scoped account binding."""

    def _instrument_metadata_for_classification(
        self,
        client: Any,
        instrument: InstrumentIdentity,
    ) -> tuple[dict[str, Any], str] | None:
        instrument_uid = str(instrument.uid or "").strip()
        if not instrument_uid:
            raise BrokerDataError("INSTRUMENT_UID_REQUIRED_FOR_CLASSIFICATION")

        method: Any
        operation: str
        source_method: str
        if instrument.instrument_type == InstrumentType.SHARE:
            method = client.instruments.share_by
            operation = "SHARE_BY"
            source_method = "ShareBy"
        elif instrument.instrument_type == InstrumentType.BOND:
            method = client.instruments.bond_by
            operation = "BOND_BY"
            source_method = "BondBy"
        elif instrument.instrument_type == InstrumentType.ETF:
            method = client.instruments.etf_by
            operation = "ETF_BY"
            source_method = "EtfBy"
        elif instrument.instrument_type == InstrumentType.CURRENCY:
            method = client.instruments.currency_by
            operation = "CURRENCY_BY"
            source_method = "CurrencyBy"
        elif instrument.instrument_type == InstrumentType.FUTURE:
            method = client.instruments.future_by
            operation = "FUTURE_BY"
            source_method = "FutureBy"
        elif instrument.instrument_type == InstrumentType.OPTION:
            method = client.instruments.option_by
            operation = "OPTION_BY"
            source_method = "OptionBy"
        elif instrument.instrument_type == InstrumentType.STRUCTURED_PRODUCT:
            method = client.instruments.structured_note_by
            operation = "STRUCTURED_NOTE_BY"
            source_method = "StructuredNoteBy"
        else:
            return None

        def lookup() -> Any:
            return method(
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_UID,
                id=instrument_uid,
            )

        response = self._call_read(operation, lookup)
        payload = _message_to_dict(response)
        raw_instrument = payload.get("instrument")
        if not isinstance(raw_instrument, dict):
            raise BrokerDataError("CLASSIFICATION_INSTRUMENT_RESPONSE_MISSING")
        actual_uid = str(raw_instrument.get("uid") or "").strip()
        if actual_uid != instrument_uid:
            raise BrokerDataError("INSTRUMENT_IDENTITY_CONFLICT")
        return dict(raw_instrument), source_method

    def _asset_detail_for_classification(
        self,
        client: Any,
        asset_uid: str,
        cache: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        cached = cache.get(asset_uid)
        if cached is not None:
            return cached

        def lookup() -> Any:
            return client.instruments.get_asset_by(id=asset_uid)

        response = self._call_read("GET_ASSET_BY", lookup)
        payload = _message_to_dict(response)
        raw_detail = payload.get("asset")
        if not isinstance(raw_detail, dict):
            raise BrokerDataError("ASSET_DETAIL_SHAPE_INVALID")
        returned_asset_uid = str(raw_detail.get("uid") or "").strip()
        if returned_asset_uid and returned_asset_uid != asset_uid:
            raise BrokerDataError("ASSET_IDENTITY_CONFLICT")
        detail = dict(raw_detail)
        cache[asset_uid] = detail
        return detail

    def read_instrument_classifications(
        self,
        instruments: tuple[InstrumentIdentity, ...],
        *,
        allow_partial: bool = False,
    ) -> tuple[TInvestInstrumentClassificationV1, ...]:
        """Resolve issuer/sector from exact reviewed T-Invest metadata reads.

        Classification uses the canonical instrument type plus stable UID to choose the
        matching point `*By` InstrumentsService method. Where that response supplies an
        asset UID, a point `GetAssetBy` read may add `brand.company`/`brand.sector`.
        Futures/options can still expose an authoritative sector directly even when no
        asset UID is available. No broad asset-list scan or ticker/name inference is used.
        """
        requested: dict[str, InstrumentIdentity] = {}
        for instrument in instruments:
            instrument_uid = str(instrument.uid or "").strip()
            if not instrument_uid:
                continue
            previous = requested.get(instrument_uid)
            if (
                previous is not None
                and previous.instrument_type != instrument.instrument_type
            ):
                raise BrokerDataError("INSTRUMENT_CLASSIFICATION_TYPE_CONFLICT")
            requested[instrument_uid] = instrument
        if not requested:
            return ()

        retrieved_at = self._clock().astimezone(timezone.utc)
        rows: list[TInvestInstrumentClassificationV1] = []
        asset_cache: dict[str, dict[str, Any]] = {}

        with self._client_factory() as client:
            self._configure_throttle(client)
            self._bind_account(client)

            for instrument_uid in sorted(requested):
                instrument = requested[instrument_uid]
                try:
                    metadata_result = self._instrument_metadata_for_classification(
                        client,
                        instrument,
                    )
                except BrokerDataError:
                    raise
                except TInvestReadAdapterError:
                    if not allow_partial:
                        raise
                    rows.append(
                        TInvestInstrumentClassificationV1(
                            instrument_uid=instrument_uid,
                            issuer=None,
                            sector=None,
                            source="T-Invest exact type-specific instrument metadata",
                            retrieved_at=retrieved_at,
                            state="UNAVAILABLE_LOOKUP",
                        )
                    )
                    continue

                if metadata_result is None:
                    rows.append(
                        TInvestInstrumentClassificationV1(
                            instrument_uid=instrument_uid,
                            issuer=None,
                            sector=None,
                            source="T-Invest classification unsupported for canonical type",
                            retrieved_at=retrieved_at,
                            state="UNAVAILABLE_ASSET_CLASS",
                        )
                    )
                    continue

                metadata, source_method = metadata_result
                direct_sector = str(metadata.get("sector") or "").strip() or None
                asset_uid = str(metadata.get("asset_uid") or "").strip()
                source = f"T-Invest {source_method}"

                if not asset_uid:
                    if not allow_partial and direct_sector is None:
                        raise BrokerDataError("INSTRUMENT_ASSET_UID_MISSING")
                    rows.append(
                        TInvestInstrumentClassificationV1(
                            instrument_uid=instrument_uid,
                            issuer=None,
                            sector=direct_sector,
                            source=f"{source}.sector; asset mapping unavailable",
                            retrieved_at=retrieved_at,
                            state=(
                                "PARTIAL"
                                if direct_sector is not None
                                else "UNAVAILABLE_MAPPING"
                            ),
                        )
                    )
                    continue

                try:
                    detail = self._asset_detail_for_classification(
                        client,
                        asset_uid,
                        asset_cache,
                    )
                except BrokerDataError:
                    raise
                except TInvestReadAdapterError:
                    if not allow_partial:
                        raise
                    rows.append(
                        TInvestInstrumentClassificationV1(
                            instrument_uid=instrument_uid,
                            issuer=None,
                            sector=direct_sector,
                            source=f"{source}.sector; GetAssetBy unavailable",
                            retrieved_at=retrieved_at,
                            state=(
                                "PARTIAL"
                                if direct_sector is not None
                                else "UNAVAILABLE_LOOKUP"
                            ),
                        )
                    )
                    continue

                brand = detail.get("brand")
                if not isinstance(brand, dict):
                    brand = {}
                issuer = str(brand.get("company") or "").strip() or None
                asset_sector = str(brand.get("sector") or "").strip() or None
                sector = asset_sector or direct_sector
                state = (
                    "VERIFIED"
                    if issuer is not None and sector is not None
                    else "PARTIAL"
                )
                rows.append(
                    TInvestInstrumentClassificationV1(
                        instrument_uid=instrument_uid,
                        issuer=issuer,
                        sector=sector,
                        source=(
                            f"{source}.asset_uid → GetAssetBy.brand"
                            f"; {source_method}.sector fallback"
                        ),
                        retrieved_at=retrieved_at,
                        state=state,
                    )
                )

        return tuple(rows)
