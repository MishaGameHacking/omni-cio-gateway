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
    _accounts,
    _binding_for_account,
    _enum_name,
    _field,
    _message_to_dict,
)
from omni_cio.contracts.v1.portfolio import InstrumentIdentity


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
        instrument_uid: str,
    ) -> dict[str, Any]:
        cached = self._instrument_cache.get(f"instrument_uid:{instrument_uid}")
        if cached is not None:
            return dict(cached)

        response = self._call_read(
            "GET_INSTRUMENT_BY",
            lambda: client.instruments.get_instrument_by(
                id_type=InstrumentIdType.INSTRUMENT_ID_TYPE_UID,
                id=instrument_uid,
            ),
        )
        payload = _message_to_dict(response)
        instrument = payload.get("instrument")
        if not isinstance(instrument, dict):
            raise BrokerDataError("INSTRUMENT_RESPONSE_MISSING")
        actual_uid = str(instrument.get("uid") or "").strip()
        if actual_uid != instrument_uid:
            raise BrokerDataError("INSTRUMENT_IDENTITY_CONFLICT")
        self._instrument_cache[f"instrument_uid:{instrument_uid}"] = dict(instrument)
        return dict(instrument)

    def read_instrument_classifications(
        self,
        instruments: tuple[InstrumentIdentity, ...],
        *,
        allow_partial: bool = False,
    ) -> tuple[TInvestInstrumentClassificationV1, ...]:
        """Resolve issuer/sector only from reviewed T-Invest asset metadata.

        The preceding snapshot normally populates the adapter's GetInstrumentBy cache.
        Classification reuses its `asset_uid`; only a cache miss performs a point lookup.
        No broad GetAssets scan or ticker/name inference is used.
        """
        requested = sorted(
            {
                str(instrument.uid or "").strip()
                for instrument in instruments
                if str(instrument.uid or "").strip()
            }
        )
        if not requested:
            return ()

        retrieved_at = self._clock().astimezone(timezone.utc)
        rows: list[TInvestInstrumentClassificationV1] = []
        detail_cache: dict[str, dict[str, Any]] = {}

        with self._client_factory() as client:
            self._configure_throttle(client)
            self._bind_account(client)

            for instrument_uid in requested:
                try:
                    instrument = self._instrument_metadata_for_classification(
                        client,
                        instrument_uid,
                    )
                    asset_uid = str(instrument.get("asset_uid") or "").strip()
                    if not asset_uid:
                        raise BrokerDataError("INSTRUMENT_ASSET_UID_MISSING")

                    detail = detail_cache.get(asset_uid)
                    if detail is None:
                        asset_response = self._call_read(
                            "GET_ASSET_BY",
                            lambda asset_uid=asset_uid: client.instruments.get_asset_by(
                                id=asset_uid
                            ),
                        )
                        payload = _message_to_dict(asset_response)
                        raw_detail = payload.get("asset")
                        if not isinstance(raw_detail, dict):
                            raise BrokerDataError("ASSET_DETAIL_SHAPE_INVALID")
                        returned_asset_uid = str(raw_detail.get("uid") or "").strip()
                        if returned_asset_uid and returned_asset_uid != asset_uid:
                            raise BrokerDataError("ASSET_IDENTITY_CONFLICT")
                        detail = raw_detail
                        detail_cache[asset_uid] = detail

                    brand = detail.get("brand")
                    if not isinstance(brand, dict):
                        brand = {}
                    issuer = str(brand.get("company") or "").strip() or None
                    sector = str(brand.get("sector") or "").strip() or None
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
                                "T-Invest GetInstrumentBy.asset_uid → "
                                "GetAssetBy.brand"
                            ),
                            retrieved_at=retrieved_at,
                            state=state,
                        )
                    )
                except Exception:
                    if not allow_partial:
                        raise
                    rows.append(
                        TInvestInstrumentClassificationV1(
                            instrument_uid=instrument_uid,
                            issuer=None,
                            sector=None,
                            source=(
                                "T-Invest GetInstrumentBy.asset_uid → "
                                "GetAssetBy.brand"
                            ),
                            retrieved_at=retrieved_at,
                            state="UNAVAILABLE_LOOKUP",
                        )
                    )

        return tuple(rows)
