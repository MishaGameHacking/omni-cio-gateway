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
        returned_instrument_uid: str | None = None,
        returned_asset_uid: str | None = None,
    ) -> None:
        self.asset_uid = asset_uid
        self.returned_instrument_uid = returned_instrument_uid
        self.returned_asset_uid = returned_asset_uid
        self.get_instrument_by_calls: list[str] = []
        self.get_asset_by_calls: list[str] = []

    def get_instrument_by(self, *, id_type: Any, id: str) -> dict[str, Any]:
        del id_type
        self.get_instrument_by_calls.append(id)
        return {
            "instrument": {
                "uid": self.returned_instrument_uid or id,
                "asset_uid": self.asset_uid,
            }
        }

    def get_asset_by(self, *, id: str) -> dict[str, Any]:
        self.get_asset_by_calls.append(id)
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


def test_classification_uses_point_instrument_asset_uid_and_asset_brand() -> None:
    instruments = FakeInstruments()
    adapter = _adapter(instruments)

    rows = adapter.read_instrument_classifications((_instrument(),))

    assert len(rows) == 1
    row = rows[0]
    assert row.instrument_uid == "instrument-uid-1"
    assert row.issuer == "Example Issuer"
    assert row.sector == "Technology"
    assert row.state == "VERIFIED"
    assert row.source == "T-Invest GetInstrumentBy.asset_uid → GetAssetBy.brand"
    assert row.retrieved_at == NOW
    assert instruments.get_instrument_by_calls == ["instrument-uid-1"]
    assert instruments.get_asset_by_calls == ["asset-uid-1"]


def test_classification_reuses_snapshot_instrument_cache() -> None:
    instruments = FakeInstruments()
    adapter = _adapter(instruments)
    adapter._instrument_cache["instrument_uid:instrument-uid-1"] = {
        "uid": "instrument-uid-1",
        "asset_uid": "asset-uid-1",
    }

    rows = adapter.read_instrument_classifications((_instrument(),))

    assert rows[0].state == "VERIFIED"
    assert instruments.get_instrument_by_calls == []
    assert instruments.get_asset_by_calls == ["asset-uid-1"]


def test_missing_asset_uid_is_explicit_in_partial_mode() -> None:
    instruments = FakeInstruments(asset_uid=None)
    adapter = _adapter(instruments)

    rows = adapter.read_instrument_classifications(
        (_instrument(kind=InstrumentType.FUTURE),),
        allow_partial=True,
    )

    assert len(rows) == 1
    assert rows[0].issuer is None
    assert rows[0].sector is None
    assert rows[0].state == "UNAVAILABLE_MAPPING"
    assert instruments.get_instrument_by_calls == ["instrument-uid-1"]
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
