from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from typing import Any, Iterator

import pytest

from omni_cio.adapters.tinvest_connection_v1 import TInvestConnectionMarketReadAdapter
from omni_cio.adapters.tinvest_read_v1 import BrokerDataError
from omni_cio.contracts.v1.portfolio import InstrumentIdentity, InstrumentType


NOW = datetime(2026, 8, 13, 8, 30, tzinfo=timezone.utc)
RAW_ACCOUNT_ID = "synthetic-owner-account"
FINGERPRINT = hashlib.sha256(RAW_ACCOUNT_ID.encode("utf-8")).hexdigest()


class FakeUsers:
    def get_user_tariff(self) -> Any:
        raise RuntimeError("tariff unavailable in deterministic fixture")

    def get_accounts(self) -> dict[str, Any]:
        return {
            "accounts": [
                {
                    "id": RAW_ACCOUNT_ID,
                    "status": 2,
                    "access_level": 2,
                    "type": "ACCOUNT_TYPE_TINKOFF",
                }
            ]
        }


class FakeInstruments:
    def __init__(
        self,
        *,
        asset_uid: str | None = "asset-uid-1",
        sector: str | None = "Technology",
        returned_instrument_uid: str | None = None,
        returned_asset_uid: str | None = None,
        asset_error: bool = False,
    ) -> None:
        self.asset_uid = asset_uid
        self.sector = sector
        self.returned_instrument_uid = returned_instrument_uid
        self.returned_asset_uid = returned_asset_uid
        self.asset_error = asset_error
        self.typed_calls: list[tuple[str, str]] = []
        self.get_asset_by_calls: list[str] = []

    def _typed_response(
        self,
        method: str,
        id: str,
        *,
        has_asset_uid: bool,
    ) -> dict[str, Any]:
        self.typed_calls.append((method, id))
        instrument: dict[str, Any] = {
            "uid": self.returned_instrument_uid or id,
            "sector": self.sector,
        }
        if has_asset_uid:
            instrument["asset_uid"] = self.asset_uid
        return {"instrument": instrument}

    def share_by(self, *, id_type: Any, id: str) -> dict[str, Any]:
        del id_type
        return self._typed_response("ShareBy", id, has_asset_uid=True)

    def bond_by(self, *, id_type: Any, id: str) -> dict[str, Any]:
        del id_type
        return self._typed_response("BondBy", id, has_asset_uid=True)

    def etf_by(self, *, id_type: Any, id: str) -> dict[str, Any]:
        del id_type
        return self._typed_response("EtfBy", id, has_asset_uid=True)

    def currency_by(self, *, id_type: Any, id: str) -> dict[str, Any]:
        del id_type
        return self._typed_response("CurrencyBy", id, has_asset_uid=True)

    def future_by(self, *, id_type: Any, id: str) -> dict[str, Any]:
        del id_type
        return self._typed_response("FutureBy", id, has_asset_uid=False)

    def option_by(self, *, id_type: Any, id: str) -> dict[str, Any]:
        del id_type
        return self._typed_response("OptionBy", id, has_asset_uid=False)

    def structured_note_by(self, *, id_type: Any, id: str) -> dict[str, Any]:
        del id_type
        return self._typed_response("StructuredNoteBy", id, has_asset_uid=True)

    def get_asset_by(self, *, id: str) -> dict[str, Any]:
        self.get_asset_by_calls.append(id)
        if self.asset_error:
            raise BrokerDataError("ASSET_PROVIDER_UNAVAILABLE")
        return {
            "asset": {
                "uid": self.returned_asset_uid or id,
                "brand": {
                    "company": "Example Issuer",
                    "sector": "Technology",
                },
            }
        }


class FakeClient:
    def __init__(self, instruments: FakeInstruments) -> None:
        self.users = FakeUsers()
        self.instruments = instruments


def _instrument(
    *,
    kind: InstrumentType = InstrumentType.SHARE,
    uid: str = "instrument-uid-1",
) -> InstrumentIdentity:
    return InstrumentIdentity(
        name="Synthetic instrument",
        instrument_type=kind,
        currency="RUB",
        lot=1,
        ticker="SYN",
        figi="BBG000000001",
        uid=uid,
        position_uid=f"position-{uid}",
        class_code="TQBR",
    )


def _adapter(instruments: FakeInstruments) -> TInvestConnectionMarketReadAdapter:
    client = FakeClient(instruments)

    @contextmanager
    def factory() -> Iterator[Any]:
        yield client

    return TInvestConnectionMarketReadAdapter(
        client_factory=factory,
        expected_account_fingerprint_sha256=FINGERPRINT,
        clock=lambda: NOW,
        monotonic=lambda: 1000.0,
        sleeper=lambda seconds: None,
        random_unit=lambda: 0.0,
    )


def test_share_classification_uses_exact_typed_read_and_asset_brand() -> None:
    instruments = FakeInstruments()
    adapter = _adapter(instruments)

    rows = adapter.read_instrument_classifications((_instrument(),))

    assert len(rows) == 1
    row = rows[0]
    assert row.instrument_uid == "instrument-uid-1"
    assert row.issuer == "Example Issuer"
    assert row.sector == "Technology"
    assert row.state == "VERIFIED"
    assert (
        row.source
        == "T-Invest ShareBy.asset_uid → GetAssetBy.brand; ShareBy.sector fallback"
    )
    assert row.retrieved_at == NOW
    assert instruments.typed_calls == [("ShareBy", "instrument-uid-1")]
    assert instruments.get_asset_by_calls == ["asset-uid-1"]


def test_future_without_asset_mapping_preserves_authoritative_sector() -> None:
    instruments = FakeInstruments()
    adapter = _adapter(instruments)

    rows = adapter.read_instrument_classifications(
        (_instrument(kind=InstrumentType.FUTURE),),
        allow_partial=True,
    )

    assert len(rows) == 1
    assert rows[0].issuer is None
    assert rows[0].sector == "Technology"
    assert rows[0].state == "PARTIAL"
    assert rows[0].source == "T-Invest FutureBy.sector; asset mapping unavailable"
    assert instruments.typed_calls == [("FutureBy", "instrument-uid-1")]
    assert instruments.get_asset_by_calls == []


def test_asset_lookup_failure_keeps_direct_sector_only_in_partial_mode() -> None:
    instruments = FakeInstruments(asset_error=True)
    adapter = _adapter(instruments)

    rows = adapter.read_instrument_classifications(
        (_instrument(),),
        allow_partial=True,
    )

    assert rows[0].issuer is None
    assert rows[0].sector == "Technology"
    assert rows[0].state == "PARTIAL"
    assert rows[0].source == "T-Invest ShareBy.sector; GetAssetBy unavailable"


def test_unsupported_canonical_type_is_explicit_without_guessing() -> None:
    instruments = FakeInstruments()
    adapter = _adapter(instruments)

    rows = adapter.read_instrument_classifications(
        (_instrument(kind=InstrumentType.OTHER),),
        allow_partial=True,
    )

    assert rows[0].issuer is None
    assert rows[0].sector is None
    assert rows[0].state == "UNAVAILABLE_ASSET_CLASS"
    assert instruments.typed_calls == []
    assert instruments.get_asset_by_calls == []


def test_instrument_identity_conflict_is_rejected() -> None:
    instruments = FakeInstruments(returned_instrument_uid="different-instrument")
    adapter = _adapter(instruments)

    with pytest.raises(BrokerDataError, match="INSTRUMENT_IDENTITY_CONFLICT"):
        adapter.read_instrument_classifications((_instrument(),))


def test_asset_identity_conflict_is_rejected() -> None:
    instruments = FakeInstruments(returned_asset_uid="different-asset")
    adapter = _adapter(instruments)

    with pytest.raises(BrokerDataError, match="ASSET_IDENTITY_CONFLICT"):
        adapter.read_instrument_classifications((_instrument(),))


def test_conflicting_types_for_same_uid_are_rejected_before_lookup() -> None:
    instruments = FakeInstruments()
    adapter = _adapter(instruments)

    with pytest.raises(
        BrokerDataError, match="INSTRUMENT_CLASSIFICATION_TYPE_CONFLICT"
    ):
        adapter.read_instrument_classifications(
            (
                _instrument(kind=InstrumentType.SHARE),
                _instrument(kind=InstrumentType.BOND),
            )
        )

    assert instruments.typed_calls == []
    assert instruments.get_asset_by_calls == []
