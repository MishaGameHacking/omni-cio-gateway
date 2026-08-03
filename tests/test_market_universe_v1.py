from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from pydantic import ValidationError
import pytest
from t_tech.invest import InstrumentStatus

from omni_cio.contracts.v1.common import Completeness, DataQuality
from omni_cio.contracts.v1.investment_policy import AccountPolicyType
from omni_cio.contracts.v1.portfolio import InstrumentIdentity, InstrumentType
from omni_cio.contracts.v1.universe import (
    REQUIRED_UNIVERSE_OPERATIONS,
    UniverseAccountEligibilityV1,
    UniverseAliasKind,
    UniverseCatalogV1,
    UniverseExclusionCode,
    UniverseFetchBatchV1,
    UniverseInstrumentV1,
    UniverseSourceOperation,
)
from omni_cio.universe.cache_v1 import UniverseCatalogCacheV1
from omni_cio.universe.engine_v1 import build_market_universe
from omni_cio.universe.service_v1 import MarketUniverseServiceV1
from omni_cio.universe.tinvest_v1 import TInvestUniverseAdapterV1


NOW = datetime(2026, 8, 3, 18, 0, tzinfo=timezone.utc)


def _instrument(
    operation: UniverseSourceOperation,
    uid: str,
    *,
    ticker: str,
    name: str | None = None,
    position_uid: str | None = None,
    figi: str | None = None,
    isin: str | None = None,
    class_code: str = "TQBR",
    api: bool = True,
    buy: bool = True,
    sell: bool = True,
    for_iis: bool = True,
    for_qual: bool = False,
    blocked_tca: bool = False,
    required_tests: tuple[str, ...] = (),
) -> UniverseInstrumentV1:
    instrument_type = {
        UniverseSourceOperation.SHARES: InstrumentType.SHARE,
        UniverseSourceOperation.BONDS: InstrumentType.BOND,
        UniverseSourceOperation.ETFS: InstrumentType.ETF,
    }[operation]
    return UniverseInstrumentV1(
        source_operation=operation,
        identity=InstrumentIdentity(
            name=name or ticker,
            instrument_type=instrument_type,
            currency="RUB",
            lot=1,
            ticker=ticker,
            class_code=class_code,
            uid=uid,
            position_uid=position_uid,
            figi=figi,
            isin=isin,
        ),
        exchange="MOEX",
        real_exchange="REAL_EXCHANGE_MOEX",
        api_trade_available=api,
        buy_available=buy,
        sell_available=sell,
        for_iis=for_iis,
        for_qual_investor=for_qual,
        blocked_tca=blocked_tca,
        required_tests=required_tests,
    )


def _catalog(
    *rows: UniverseInstrumentV1,
    completed: tuple[UniverseSourceOperation, ...] = REQUIRED_UNIVERSE_OPERATIONS,
    source_errors: tuple[str, ...] = (),
    invalid_rows: int = 0,
) -> UniverseCatalogV1:
    return UniverseCatalogV1(
        retrieved_at=NOW,
        completed_operations=completed,
        instruments=rows,
        source_errors=source_errors,
        invalid_rows=invalid_rows,
    )


def _account(
    *,
    account_type: AccountPolicyType = AccountPolicyType.BROKERAGE,
    qualified: bool | None = False,
) -> UniverseAccountEligibilityV1:
    return UniverseAccountEligibilityV1(
        account_type=account_type,
        qualified_investor=qualified,
    )


def _batch(
    *rows: UniverseInstrumentV1,
    account: UniverseAccountEligibilityV1 | None = None,
    completed: tuple[UniverseSourceOperation, ...] = REQUIRED_UNIVERSE_OPERATIONS,
    source_errors: tuple[str, ...] = (),
    invalid_rows: int = 0,
    account_source_error: str | None = None,
) -> UniverseFetchBatchV1:
    return UniverseFetchBatchV1(
        catalog=_catalog(
            *rows,
            completed=completed,
            source_errors=source_errors,
            invalid_rows=invalid_rows,
        ),
        account=account or _account(),
        account_source_error=account_source_error,
    )


def test_complete_broker_universe_is_decision_ready() -> None:
    snapshot = build_market_universe(
        _batch(
            _instrument(UniverseSourceOperation.SHARES, "uid-share", ticker="SBER"),
            _instrument(UniverseSourceOperation.BONDS, "uid-bond", ticker="BOND"),
            _instrument(UniverseSourceOperation.ETFS, "uid-etf", ticker="LQDT"),
        )
    )

    assert snapshot.decision_ready is True
    assert snapshot.quality.quality is DataQuality.VERIFIED
    assert snapshot.quality.completeness is Completeness.COMPLETE
    assert len(snapshot.instruments) == 3
    assert snapshot.excluded == ()
    assert snapshot.conflicts == ()


def test_exact_duplicate_rows_are_removed_and_counted() -> None:
    share = _instrument(UniverseSourceOperation.SHARES, "uid-share", ticker="SBER")
    snapshot = build_market_universe(_batch(share, share))

    assert snapshot.decision_ready is True
    assert len(snapshot.instruments) == 1
    assert snapshot.duplicate_rows_removed == 1
    share_count = next(
        row
        for row in snapshot.source_counts
        if row.operation is UniverseSourceOperation.SHARES
    )
    assert share_count.received == 2
    assert share_count.unique == 1
    assert share_count.duplicates_removed == 1


def test_same_uid_with_different_payload_fails_closed() -> None:
    first = _instrument(
        UniverseSourceOperation.SHARES,
        "UID-SAME",
        ticker="AAA",
        name="First",
    )
    second = _instrument(
        UniverseSourceOperation.SHARES,
        "UID-SAME",
        ticker="AAA",
        name="Second",
    )

    snapshot = build_market_universe(_batch(first, second))

    assert snapshot.decision_ready is False
    assert any(
        row.alias_kind is UniverseAliasKind.UID_PAYLOAD
        for row in snapshot.conflicts
    )


def test_stable_alias_mapping_to_multiple_uids_fails_closed() -> None:
    first = _instrument(
        UniverseSourceOperation.SHARES,
        "uid-one",
        ticker="SAME",
        position_uid="pos-same",
        figi="BBG000SAME1",
    )
    second = _instrument(
        UniverseSourceOperation.SHARES,
        "uid-two",
        ticker="SAME",
        position_uid="pos-same",
        figi="BBG000SAME1",
    )

    snapshot = build_market_universe(_batch(first, second))

    kinds = {row.alias_kind for row in snapshot.conflicts}
    assert UniverseAliasKind.POSITION_UID in kinds
    assert UniverseAliasKind.FIGI in kinds
    assert UniverseAliasKind.TICKER_CLASS_CODE in kinds
    assert snapshot.decision_ready is False


def test_eligibility_reasons_are_deterministic_and_account_aware() -> None:
    blocked = _instrument(
        UniverseSourceOperation.SHARES,
        "uid-blocked",
        ticker="BLOCK",
        api=False,
        buy=False,
        for_iis=False,
        for_qual=True,
        blocked_tca=True,
        required_tests=("test_a",),
    )
    snapshot = build_market_universe(
        _batch(
            blocked,
            account=_account(
                account_type=AccountPolicyType.IIS,
                qualified=False,
            ),
        )
    )

    assert snapshot.decision_ready is False
    assert len(snapshot.excluded) == 1
    assert set(snapshot.excluded[0].reasons) == {
        UniverseExclusionCode.API_NOT_AVAILABLE,
        UniverseExclusionCode.BUY_NOT_AVAILABLE,
        UniverseExclusionCode.IIS_NOT_ALLOWED,
        UniverseExclusionCode.QUALIFICATION_REQUIRED,
        UniverseExclusionCode.REQUIRED_TESTS_MISSING,
        UniverseExclusionCode.BLOCKED_TCA,
    }


def test_qualified_investor_can_pass_qualification_gate() -> None:
    row = _instrument(
        UniverseSourceOperation.SHARES,
        "uid-qual",
        ticker="QUAL",
        for_qual=True,
    )
    snapshot = build_market_universe(
        _batch(row, account=_account(qualified=True))
    )

    assert snapshot.decision_ready is True
    assert snapshot.instruments == (row,)


def test_missing_tests_remain_a_block_even_if_user_has_other_permissions() -> None:
    row = _instrument(
        UniverseSourceOperation.SHARES,
        "uid-test",
        ticker="TEST",
        required_tests=("needed_test",),
    )
    account = UniverseAccountEligibilityV1(
        account_type=AccountPolicyType.BROKERAGE,
        qualified_investor=False,
        qualified_for_work_with=("other_test",),
    )

    snapshot = build_market_universe(_batch(row, account=account))

    assert snapshot.decision_ready is False
    assert UniverseExclusionCode.REQUIRED_TESTS_MISSING in snapshot.excluded[0].reasons


def test_catalog_or_account_source_failure_is_never_silently_ready() -> None:
    row = _instrument(UniverseSourceOperation.SHARES, "uid-share", ticker="SBER")
    source_failure = build_market_universe(
        _batch(
            row,
            completed=(UniverseSourceOperation.SHARES,),
            source_errors=("Bonds:TimeoutError",),
        )
    )
    account_failure = build_market_universe(
        _batch(
            row,
            account=_account(qualified=None),
            account_source_error="GetInfo:TimeoutError",
        )
    )

    assert source_failure.decision_ready is False
    assert source_failure.quality.quality is DataQuality.DEGRADED
    assert account_failure.decision_ready is False


def test_unknown_account_type_or_qualification_fails_closed() -> None:
    row = _instrument(UniverseSourceOperation.SHARES, "uid-share", ticker="SBER")
    unknown_type = build_market_universe(
        _batch(row, account=_account(account_type=AccountPolicyType.UNKNOWN))
    )
    unknown_qual = build_market_universe(
        _batch(row, account=_account(qualified=None))
    )

    assert unknown_type.decision_ready is False
    assert unknown_qual.decision_ready is False


def test_content_fingerprint_is_order_and_retrieval_time_invariant() -> None:
    share = _instrument(UniverseSourceOperation.SHARES, "uid-share", ticker="SBER")
    bond = _instrument(UniverseSourceOperation.BONDS, "uid-bond", ticker="BOND")
    first = build_market_universe(_batch(share, bond))
    second_catalog = UniverseCatalogV1(
        retrieved_at=datetime(2026, 8, 3, 19, 0, tzinfo=timezone.utc),
        completed_operations=tuple(reversed(REQUIRED_UNIVERSE_OPERATIONS)),
        instruments=(bond, share),
    )
    second = build_market_universe(
        UniverseFetchBatchV1(catalog=second_catalog, account=_account())
    )

    assert first.content_sha256 == second.content_sha256


def test_content_fingerprint_changes_on_material_instrument_change() -> None:
    first = build_market_universe(
        _batch(_instrument(UniverseSourceOperation.SHARES, "uid-share", ticker="SBER"))
    )
    second = build_market_universe(
        _batch(
            _instrument(
                UniverseSourceOperation.SHARES,
                "uid-share",
                ticker="SBER",
                buy=False,
            )
        )
    )

    assert first.content_sha256 != second.content_sha256


def test_universe_contract_rejects_account_identifiers_as_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        UniverseAccountEligibilityV1.model_validate(
            {
                "account_type": "brokerage",
                "qualified_investor": False,
                "account_id": "1234567890",
            }
        )


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class _CatalogLoader:
    def __init__(self, catalog: UniverseCatalogV1) -> None:
        self.catalog = catalog
        self.calls = 0

    def __call__(self) -> UniverseCatalogV1:
        self.calls += 1
        return self.catalog


def test_catalog_cache_reuses_verified_catalog_until_ttl_or_force_refresh() -> None:
    clock = _Clock()
    loader = _CatalogLoader(
        _catalog(_instrument(UniverseSourceOperation.SHARES, "uid", ticker="AAA"))
    )
    cache = UniverseCatalogCacheV1(ttl_seconds=10, clock=clock)

    first = cache.get_or_refresh(loader)
    second = cache.get_or_refresh(loader)
    clock.value = 11
    third = cache.get_or_refresh(loader)
    fourth = cache.get_or_refresh(loader, force_refresh=True)

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert third.cache_hit is False
    assert fourth.cache_hit is False
    assert loader.calls == 3


def test_catalog_cache_never_caches_partial_or_invalid_catalog() -> None:
    partial_loader = _CatalogLoader(
        _catalog(
            completed=(UniverseSourceOperation.SHARES,),
            source_errors=("Bonds:TimeoutError",),
        )
    )
    invalid_loader = _CatalogLoader(_catalog(invalid_rows=1))
    cache = UniverseCatalogCacheV1(ttl_seconds=10)

    assert cache.get_or_refresh(partial_loader).cache_hit is False
    assert cache.get_or_refresh(partial_loader).cache_hit is False
    assert partial_loader.calls == 2

    assert cache.get_or_refresh(invalid_loader).cache_hit is False
    assert cache.get_or_refresh(invalid_loader).cache_hit is False
    assert invalid_loader.calls == 2


class _FakeInstruments:
    def __init__(self, rows: dict[str, list[object]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, object]] = []

    def _response(self, method: str, instrument_status: object) -> object:
        self.calls.append((method, instrument_status))
        return SimpleNamespace(instruments=self.rows.get(method, []))

    def shares(self, *, instrument_status: object) -> object:
        return self._response("shares", instrument_status)

    def bonds(self, *, instrument_status: object) -> object:
        return self._response("bonds", instrument_status)

    def etfs(self, *, instrument_status: object) -> object:
        return self._response("etfs", instrument_status)


class _FakeUsers:
    def __init__(self, *, qual_status: bool = False) -> None:
        self.qual_status = qual_status
        self.calls = 0

    def get_info(self) -> object:
        self.calls += 1
        return SimpleNamespace(
            qual_status=self.qual_status,
            qualified_for_work_with=["test_passed"],
            user_id="must-not-be-persisted",
        )


class _FakeClient:
    def __init__(self, instruments: _FakeInstruments, users: _FakeUsers) -> None:
        self.instruments = instruments
        self.users = users


class _FakeContext:
    def __init__(self, client: _FakeClient) -> None:
        self.client = client

    def __enter__(self) -> _FakeClient:
        return self.client

    def __exit__(self, *args: object) -> None:
        return None


class _FakeFactory:
    def __init__(self, client: _FakeClient) -> None:
        self.client = client
        self.tokens: list[str] = []

    def __call__(self, token: str) -> _FakeContext:
        self.tokens.append(token)
        return _FakeContext(self.client)


def _sdk_row(uid: str, ticker: str) -> object:
    return SimpleNamespace(
        name=ticker,
        currency="rub",
        lot=1,
        ticker=ticker,
        class_code="TQBR",
        isin="",
        figi=f"FIGI-{uid}",
        uid=uid,
        position_uid=f"POS-{uid}",
        exchange="MOEX",
        real_exchange="REAL_EXCHANGE_MOEX",
        api_trade_available_flag=True,
        buy_available_flag=True,
        sell_available_flag=True,
        for_iis_flag=True,
        for_qual_investor_flag=False,
        blocked_tca_flag=False,
        otc_flag=False,
        liquidity_flag=True,
        required_tests=[],
    )


def test_tinvest_adapter_enumerates_base_shares_bonds_etfs_only() -> None:
    instruments = _FakeInstruments(
        {
            "shares": [_sdk_row("share-uid", "SBER")],
            "bonds": [_sdk_row("bond-uid", "BOND")],
            "etfs": [_sdk_row("etf-uid", "LQDT")],
        }
    )
    users = _FakeUsers(qual_status=False)
    factory = _FakeFactory(_FakeClient(instruments, users))
    adapter = TInvestUniverseAdapterV1("test-token", client_factory=factory)

    catalog = adapter.fetch_catalog(retrieved_at=NOW)
    account, error = adapter.fetch_account_eligibility(
        account_type=AccountPolicyType.BROKERAGE
    )

    assert catalog.completed_operations == REQUIRED_UNIVERSE_OPERATIONS
    assert len(catalog.instruments) == 3
    assert catalog.source_errors == ()
    assert catalog.invalid_rows == 0
    assert [call[0] for call in instruments.calls] == ["shares", "bonds", "etfs"]
    assert all(
        status is InstrumentStatus.INSTRUMENT_STATUS_BASE
        for _, status in instruments.calls
    )
    assert account.qualified_investor is False
    assert account.qualified_for_work_with == ("test_passed",)
    assert error is None
    assert "user_id" not in account.model_dump(mode="json")


def test_tinvest_adapter_invalid_row_degrades_catalog_without_raw_error() -> None:
    bad = _sdk_row("bad-uid", "BAD")
    delattr(bad, "blocked_tca_flag")
    instruments = _FakeInstruments({"shares": [bad], "bonds": [], "etfs": []})
    adapter = TInvestUniverseAdapterV1(
        "secret-token",
        client_factory=_FakeFactory(_FakeClient(instruments, _FakeUsers())),
    )

    catalog = adapter.fetch_catalog(retrieved_at=NOW)
    snapshot = build_market_universe(
        UniverseFetchBatchV1(catalog=catalog, account=_account())
    )

    assert catalog.invalid_rows == 1
    assert snapshot.decision_ready is False
    assert "secret-token" not in str(catalog.model_dump(mode="json"))


class _BrokenFactory:
    def __call__(self, token: str) -> Any:
        raise RuntimeError(f"transport failure {token}")


def test_tinvest_adapter_transport_failure_returns_generic_unavailable_catalog() -> None:
    adapter = TInvestUniverseAdapterV1(
        "private-token",
        client_factory=_BrokenFactory(),
    )

    catalog = adapter.fetch_catalog(retrieved_at=NOW)
    account, account_error = adapter.fetch_account_eligibility(
        account_type=AccountPolicyType.BROKERAGE
    )

    assert catalog.completed_operations == ()
    assert len(catalog.source_errors) == 3
    assert all("private-token" not in item for item in catalog.source_errors)
    assert account.qualified_investor is None
    assert account_error == "GetInfo:RuntimeError"


class _ServiceAdapter:
    def __init__(self, catalog: UniverseCatalogV1) -> None:
        self.catalog = catalog
        self.catalog_calls = 0
        self.account_calls = 0

    def fetch_catalog(self, *, retrieved_at: datetime | None = None) -> UniverseCatalogV1:
        self.catalog_calls += 1
        return self.catalog

    def fetch_account_eligibility(
        self,
        *,
        account_type: AccountPolicyType,
    ) -> tuple[UniverseAccountEligibilityV1, str | None]:
        self.account_calls += 1
        return _account(account_type=account_type), None


def test_service_refreshes_account_eligibility_even_on_catalog_cache_hit() -> None:
    adapter = _ServiceAdapter(
        _catalog(_instrument(UniverseSourceOperation.SHARES, "uid", ticker="AAA"))
    )
    service = MarketUniverseServiceV1(
        adapter,
        cache=UniverseCatalogCacheV1(ttl_seconds=100),
    )

    first = service.load(account_type=AccountPolicyType.BROKERAGE)
    second = service.load(account_type=AccountPolicyType.BROKERAGE)

    assert first.catalog_cache_hit is False
    assert second.catalog_cache_hit is True
    assert adapter.catalog_calls == 1
    assert adapter.account_calls == 2
