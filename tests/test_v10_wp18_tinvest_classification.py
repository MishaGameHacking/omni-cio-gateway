from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
from types import SimpleNamespace
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
    def __init__(self, *, duplicate_mapping: bool = False) -> None:
        self.duplicate_mapping = duplicate_mapping
        self.get_assets_calls = 0
        self.get_asset_by_calls: list[str] = []

    def get_assets(self) -> dict[str, Any]:
        self.get_assets_calls += 1
        assets = [
            {
                "uid": "asset-uid-1",
                "instruments": [{"uid": "instrument-uid-1"}],
            }
        ]
        if self.duplicate_mapping:
            assets.append(
                {
                    "uid": "asset-uid-conflict",
                    "instruments": [{"uid": "instrument-uid-1"}],
                }
            )
        return {"assets": assets}

    def get_asset_by(self, *, id: str) -> dict[str, Any]:
        self.get_asset_by_calls.append(id)
        return {
            "asset": {
                "uid": id,
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


def test_classification_uses_asset_brand_company_and_sector() -> None:
    instruments = FakeInstruments()
    adapter = _adapter(instruments)

    rows = adapter.read_instrument_classifications((_instrument(),))

    assert len(rows) == 1
    row = rows[0]
    assert row.instrument_uid == "instrument-uid-1"
    assert row.issuer == "Example Issuer"
    assert row.sector == "Technology"
    assert row.state == "VERIFIED"
    assert row.source == "T-Invest GetAssets → GetAssetBy.brand"
    assert row.retrieved_at == NOW
    assert instruments.get_assets_calls == 1
    assert instruments.get_asset_by_calls == ["asset-uid-1"]


def test_future_classification_fails_closed_without_asset_lookup() -> None:
    instruments = FakeInstruments()
    adapter = _adapter(instruments)

    rows = adapter.read_instrument_classifications(
        (_instrument(kind=InstrumentType.FUTURE),),
        allow_partial=True,
    )

    assert len(rows) == 1
    assert rows[0].issuer is None
    assert rows[0].sector is None
    assert rows[0].state == "UNAVAILABLE_ASSET_CLASS"
    assert instruments.get_assets_calls == 0
    assert instruments.get_asset_by_calls == []


def test_missing_asset_mapping_is_explicit_in_partial_mode() -> None:
    instruments = FakeInstruments()
    adapter = _adapter(instruments)

    rows = adapter.read_instrument_classifications(
        (_instrument(uid="instrument-not-in-assets"),),
        allow_partial=True,
    )

    assert len(rows) == 1
    assert rows[0].state == "UNAVAILABLE_MAPPING"
    assert rows[0].issuer is None
    assert rows[0].sector is None
    assert instruments.get_asset_by_calls == []


def test_conflicting_asset_mapping_is_rejected() -> None:
    instruments = FakeInstruments(duplicate_mapping=True)
    adapter = _adapter(instruments)

    with pytest.raises(BrokerDataError, match="INSTRUMENT_ASSET_IDENTITY_CONFLICT"):
        adapter.read_instrument_classifications((_instrument(),), allow_partial=True)
