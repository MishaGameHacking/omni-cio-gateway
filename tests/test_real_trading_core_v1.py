from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest

from omni_cio.real_trading.client_v1 import RealTradingApiFailure, RealTradingRestClientV1
from omni_cio.real_trading.journal_v1 import InMemoryRealExecutionJournalV1
from omni_cio.real_trading.models_v1 import RealMarketContextV1, RealTradingPolicyV1
from omni_cio.real_trading.service_v1 import RealTradingServiceV1, sanitized_json


ACCOUNT_ID = "real-account-1234"
INSTRUMENT_UID = "e6123145-9665-43e0-8413-cd61b8aa9b13"
BASE_TIME = datetime(2026, 8, 3, 7, 0, 0, tzinfo=timezone.utc)


class FakeBroker:
    base_url = "https://invest-public-api.tbank.ru/rest"

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.accounts: list[dict[str, Any]] = [
            {"id": ACCOUNT_ID, "status": "ACCOUNT_STATUS_OPEN"}
        ]
        self.buy_max_lots = 10
        self.sell_max_lots = 10
        self.preview_total = Decimal("1000")
        self.preview_commission = Decimal("1")
        self.post_failure: RealTradingApiFailure | None = None

    def post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((method, payload))
        if method == "GetAccounts":
            return {"accounts": self.accounts}
        if method == "GetMaxLots":
            return {
                "currency": "rub",
                "buyLimits": {"buyMaxLots": str(self.buy_max_lots)},
                "buyMarginLimits": {"buyMaxLots": "999999"},
                "sellLimits": {"sellMaxLots": str(self.sell_max_lots)},
                "sellMarginLimits": {"sellMaxLots": "999999"},
            }
        if method == "GetOrderPrice":
            return {
                "totalOrderAmount": money(self.preview_total),
                "executedCommissionRub": money(self.preview_commission),
            }
        if method == "PostOrder":
            if self.post_failure is not None:
                raise self.post_failure
            return {
                "orderId": "broker-order-id",
                "accountId": ACCOUNT_ID,
                "executionReportStatus": "EXECUTION_REPORT_STATUS_NEW",
            }
        if method == "GetOrderState":
            return {
                "orderId": "broker-order-id",
                "orderRequestId": payload["orderId"],
                "accountId": ACCOUNT_ID,
                "executionReportStatus": "EXECUTION_REPORT_STATUS_NEW",
            }
        raise AssertionError(f"unexpected method {method}")


def money(value: Decimal) -> dict[str, Any]:
    quantized = value.quantize(Decimal("0.000000001"))
    units = int(quantized)
    nano = int((quantized - Decimal(units)) * Decimal("1000000000"))
    return {"currency": "rub", "units": str(units), "nano": nano}


class MarketSequence:
    def __init__(
        self,
        times: list[datetime],
        *,
        min_price_increment: Decimal = Decimal("0.01"),
    ) -> None:
        self._times = list(times)
        self._min_price_increment = min_price_increment
        self.calls = 0

    def __call__(self, instrument_uid: str) -> RealMarketContextV1:
        index = min(self.calls, len(self._times) - 1)
        self.calls += 1
        return RealMarketContextV1(
            instrument_uid=instrument_uid,
            ticker="SBER",
            isin="RU0009029540",
            instrument_type="share",
            lot=1,
            currency="RUB",
            min_price_increment=self._min_price_increment,
            api_trade_available=True,
            limit_orders_available=True,
            trading_status="SECURITY_TRADING_STATUS_NORMAL_TRADING",
            retrieved_at=self._times[index],
            complete=True,
        )


def policy(*, daily: str = "5000", order: str = "2000") -> RealTradingPolicyV1:
    return RealTradingPolicyV1(
        max_order_rub=Decimal(order),
        max_daily_rub=Decimal(daily),
        confirmation_ttl_seconds=120,
        market_max_age_seconds=15,
    )


def service(
    broker: FakeBroker | None = None,
    market: MarketSequence | None = None,
    journal: InMemoryRealExecutionJournalV1 | None = None,
    *,
    daily: str = "5000",
    order: str = "2000",
) -> tuple[RealTradingServiceV1, FakeBroker, InMemoryRealExecutionJournalV1]:
    broker = broker or FakeBroker()
    journal = journal or InMemoryRealExecutionJournalV1()
    market = market or MarketSequence(
        [BASE_TIME - timedelta(seconds=1), BASE_TIME + timedelta(seconds=9)]
    )
    result = RealTradingServiceV1(
        token="dedicated-trading-token",  # pragma: allowlist secret
        gateway_secret="gateway-secret",  # pragma: allowlist secret
        expected_account_id=ACCOUNT_ID,
        policy=policy(daily=daily, order=order),
        journal=journal,
        market_context_provider=market,
        client=broker,
        require_durable_journal=False,
    )
    return result, broker, journal


def prepare(svc: RealTradingServiceV1):
    return svc.prepare_trade(
        instrument_uid=INSTRUMENT_UID,
        direction="BUY",
        quantity_lots=1,
        limit_price="270",
        rationale="Phase 1 fake-client acceptance test",
        now=BASE_TIME,
    )


def test_production_constructor_requires_durable_journal() -> None:
    broker = FakeBroker()
    journal = InMemoryRealExecutionJournalV1()
    with pytest.raises(RealTradingApiFailure) as exc_info:
        RealTradingServiceV1(
            token="dedicated",  # pragma: allowlist secret
            gateway_secret="secret",  # pragma: allowlist secret
            expected_account_id=ACCOUNT_ID,
            policy=policy(),
            journal=journal,
            market_context_provider=MarketSequence([BASE_TIME]),
            client=broker,
        )
    assert exc_info.value.code == "REAL_DURABLE_JOURNAL_REQUIRED"


def test_policy_rejects_values_above_v1_absolute_ceiling() -> None:
    with pytest.raises(RealTradingApiFailure) as exc_info:
        RealTradingServiceV1(
            token="dedicated",  # pragma: allowlist secret
            gateway_secret="secret",  # pragma: allowlist secret
            expected_account_id=ACCOUNT_ID,
            policy=policy(daily="300001", order="100001"),
            journal=InMemoryRealExecutionJournalV1(),
            market_context_provider=MarketSequence([BASE_TIME]),
            client=FakeBroker(),
            require_durable_journal=False,
        )
    assert exc_info.value.code == "REAL_TRADING_POLICY_INVALID"


def test_real_rest_client_has_fixed_host_and_method_allowlist() -> None:
    client = RealTradingRestClientV1("dedicated")
    assert client.base_url == "https://invest-public-api.tbank.ru/rest"
    with pytest.raises(RealTradingApiFailure) as exc_info:
        client._url("ReplaceOrder")
    assert exc_info.value.code == "REAL_TRADING_METHOD_NOT_ALLOWED"


def test_prepare_is_limit_only_and_does_not_submit() -> None:
    svc, broker, _ = service()
    proposal = prepare(svc)
    assert proposal.state == "prepared"
    assert proposal.limit_price == Decimal("270")
    assert proposal.preview_total_rub == Decimal("1000")
    assert proposal.preview_commission_rub == Decimal("1")
    assert proposal.available_lots == 10
    assert proposal.confirmation_phrase.startswith("ПОДТВЕРЖДАЮ РЕАЛЬНУЮ СДЕЛКУ ")
    assert "PostOrder" not in [method for method, _ in broker.calls]


def test_limit_price_must_match_instrument_price_step() -> None:
    market = MarketSequence(
        [BASE_TIME - timedelta(seconds=1)],
        min_price_increment=Decimal("0.05"),
    )
    svc, broker, _ = service(market=market)
    with pytest.raises(RealTradingApiFailure) as exc_info:
        svc.prepare_trade(
            instrument_uid=INSTRUMENT_UID,
            direction="BUY",
            quantity_lots=1,
            limit_price="270.03",
            rationale="price-step rejection",
            now=BASE_TIME,
        )
    assert exc_info.value.code == "REAL_PRICE_STEP_MISMATCH"
    assert "PostOrder" not in [method for method, _ in broker.calls]


def test_wrong_confirmation_never_submits() -> None:
    svc, broker, _ = service()
    proposal = prepare(svc)
    with pytest.raises(RealTradingApiFailure) as exc_info:
        svc.execute_trade(
            proposal.proposal_id,
            "ПОДТВЕРЖДАЮ РЕАЛЬНУЮ СДЕЛКУ WRONG",
            now=BASE_TIME + timedelta(seconds=10),
        )
    assert exc_info.value.code == "REAL_CONFIRMATION_MISMATCH"
    assert "PostOrder" not in [method for method, _ in broker.calls]


def test_expired_confirmation_never_submits() -> None:
    svc, broker, journal = service()
    proposal = prepare(svc)
    with pytest.raises(RealTradingApiFailure) as exc_info:
        svc.execute_trade(
            proposal.proposal_id,
            proposal.confirmation_phrase,
            now=BASE_TIME + timedelta(seconds=121),
        )
    assert exc_info.value.code == "REAL_CONFIRMATION_EXPIRED"
    assert journal.get(proposal.proposal_id).state == "expired"
    assert "PostOrder" not in [method for method, _ in broker.calls]


def test_execute_submits_limit_day_currency_without_margin() -> None:
    svc, broker, journal = service()
    proposal = prepare(svc)
    completed, replay = svc.execute_trade(
        proposal.proposal_id,
        proposal.confirmation_phrase,
        now=BASE_TIME + timedelta(seconds=10),
    )
    assert replay is False
    assert completed.state == "submitted"
    post_payloads = [payload for method, payload in broker.calls if method == "PostOrder"]
    assert len(post_payloads) == 1
    payload = post_payloads[0]
    assert payload["orderType"] == "ORDER_TYPE_LIMIT"
    assert payload["timeInForce"] == "TIME_IN_FORCE_DAY"
    assert payload["priceType"] == "PRICE_TYPE_CURRENCY"
    assert payload["confirmMarginTrade"] is False
    assert payload["orderId"] == proposal.order_id
    assert ACCOUNT_ID not in (journal.get(proposal.proposal_id).broker_response_json or "")
    assert "***1234" in (journal.get(proposal.proposal_id).broker_response_json or "")


def test_successful_replay_does_not_submit_twice() -> None:
    svc, broker, _ = service()
    proposal = prepare(svc)
    svc.execute_trade(
        proposal.proposal_id,
        proposal.confirmation_phrase,
        now=BASE_TIME + timedelta(seconds=10),
    )
    completed, replay = svc.execute_trade(
        proposal.proposal_id,
        proposal.confirmation_phrase,
        now=BASE_TIME + timedelta(seconds=11),
    )
    assert completed.state == "submitted"
    assert replay is True
    assert [method for method, _ in broker.calls].count("PostOrder") == 1


def test_ambiguous_submit_is_never_retried_and_can_be_reconciled() -> None:
    broker = FakeBroker()
    broker.post_failure = RealTradingApiFailure(
        code="REAL_TRADING_TRANSPORT_AMBIGUOUS",
        message="TimeoutException",
        http_status=503,
        ambiguous_submission=True,
    )
    svc, broker, journal = service(broker=broker)
    proposal = prepare(svc)
    with pytest.raises(RealTradingApiFailure) as first:
        svc.execute_trade(
            proposal.proposal_id,
            proposal.confirmation_phrase,
            now=BASE_TIME + timedelta(seconds=10),
        )
    assert first.value.ambiguous_submission is True
    assert journal.get(proposal.proposal_id).state == "unknown"

    with pytest.raises(RealTradingApiFailure) as second:
        svc.execute_trade(
            proposal.proposal_id,
            proposal.confirmation_phrase,
            now=BASE_TIME + timedelta(seconds=11),
        )
    assert second.value.code == "REAL_ORDER_SUBMISSION_UNCERTAIN"
    assert [method for method, _ in broker.calls].count("PostOrder") == 1

    reconciled = svc.reconcile_proposal(proposal.proposal_id)
    assert reconciled.state == "submitted"
    assert [method for method, _ in broker.calls].count("PostOrder") == 1
    assert [method for method, _ in broker.calls].count("GetOrderState") == 1


def test_buy_uses_own_funds_not_margin_limit() -> None:
    broker = FakeBroker()
    broker.buy_max_lots = 0
    svc, broker, _ = service(broker=broker)
    with pytest.raises(RealTradingApiFailure) as exc_info:
        prepare(svc)
    assert exc_info.value.code == "REAL_QUANTITY_EXCEEDS_LIMIT"
    assert "PostOrder" not in [method for method, _ in broker.calls]


def test_sell_uses_own_position_not_margin_limit() -> None:
    broker = FakeBroker()
    broker.sell_max_lots = 0
    svc, broker, _ = service(broker=broker)
    with pytest.raises(RealTradingApiFailure) as exc_info:
        svc.prepare_trade(
            instrument_uid=INSTRUMENT_UID,
            direction="SELL",
            quantity_lots=1,
            limit_price="270",
            rationale="No short sales",
            now=BASE_TIME,
        )
    assert exc_info.value.code == "REAL_QUANTITY_EXCEEDS_LIMIT"
    assert "PostOrder" not in [method for method, _ in broker.calls]


def test_order_hard_cap_blocks_before_submit() -> None:
    svc, broker, _ = service(order="999", daily="5000")
    with pytest.raises(RealTradingApiFailure) as exc_info:
        prepare(svc)
    assert exc_info.value.code == "REAL_ORDER_CAP_EXCEEDED"
    assert "PostOrder" not in [method for method, _ in broker.calls]


def test_daily_hard_cap_counts_prior_submitted_notional() -> None:
    svc, broker, _ = service(daily="1500", order="1000")
    proposal = prepare(svc)
    svc.execute_trade(
        proposal.proposal_id,
        proposal.confirmation_phrase,
        now=BASE_TIME + timedelta(seconds=10),
    )
    with pytest.raises(RealTradingApiFailure) as exc_info:
        svc.prepare_trade(
            instrument_uid=INSTRUMENT_UID,
            direction="BUY",
            quantity_lots=1,
            limit_price="270",
            rationale="Second order should exceed daily cap",
            now=BASE_TIME + timedelta(seconds=20),
        )
    assert exc_info.value.code == "REAL_DAILY_CAP_EXCEEDED"
    assert [method for method, _ in broker.calls].count("PostOrder") == 1


def test_account_mismatch_fails_closed() -> None:
    broker = FakeBroker()
    broker.accounts = [{"id": "different-account", "status": "ACCOUNT_STATUS_OPEN"}]
    svc, broker, _ = service(broker=broker)
    with pytest.raises(RealTradingApiFailure) as exc_info:
        prepare(svc)
    assert exc_info.value.code == "REAL_ACCOUNT_BINDING_MISMATCH"
    assert "PostOrder" not in [method for method, _ in broker.calls]


def test_multiple_accounts_fail_closed() -> None:
    broker = FakeBroker()
    broker.accounts.append({"id": "other-account", "status": "ACCOUNT_STATUS_OPEN"})
    svc, broker, _ = service(broker=broker)
    with pytest.raises(RealTradingApiFailure) as exc_info:
        prepare(svc)
    assert exc_info.value.code == "REAL_ACCOUNT_BINDING_AMBIGUOUS"
    assert "PostOrder" not in [method for method, _ in broker.calls]


def test_stale_market_fails_closed() -> None:
    stale = MarketSequence([BASE_TIME - timedelta(seconds=16)])
    svc, broker, _ = service(market=stale)
    with pytest.raises(RealTradingApiFailure) as exc_info:
        prepare(svc)
    assert exc_info.value.code == "REAL_MARKET_DATA_STALE"
    assert "PostOrder" not in [method for method, _ in broker.calls]


def test_preflight_change_requires_fresh_proposal() -> None:
    broker = FakeBroker()
    market = MarketSequence(
        [BASE_TIME - timedelta(seconds=1), BASE_TIME + timedelta(seconds=9)]
    )
    svc, broker, _ = service(broker=broker, market=market)
    proposal = prepare(svc)
    broker.preview_total = Decimal("1001")
    with pytest.raises(RealTradingApiFailure) as exc_info:
        svc.execute_trade(
            proposal.proposal_id,
            proposal.confirmation_phrase,
            now=BASE_TIME + timedelta(seconds=10),
        )
    assert exc_info.value.code == "REAL_PREFLIGHT_CHANGED"
    assert "PostOrder" not in [method for method, _ in broker.calls]


def test_order_state_reconciles_by_request_id_and_masks_account() -> None:
    svc, broker, _ = service()
    result = svc.order_state("11111111-1111-4111-8111-111111111111")
    assert result["masked_account"] == "***1234"
    assert ACCOUNT_ID not in result["broker_response_json"]
    state_payloads = [payload for method, payload in broker.calls if method == "GetOrderState"]
    assert state_payloads[0]["orderIdType"] == "ORDER_ID_TYPE_REQUEST"


def test_sanitizer_redacts_sensitive_keys_recursively() -> None:
    payload = {
        "accountId": ACCOUNT_ID,
        "token": "secret-token",  # pragma: allowlist secret
        "nested": {"Authorization": "Bearer secret"},  # pragma: allowlist secret
    }
    encoded = sanitized_json(payload)
    assert ACCOUNT_ID not in encoded
    assert "secret-token" not in encoded  # pragma: allowlist secret
    assert "Bearer secret" not in encoded  # pragma: allowlist secret
    assert "***1234" in encoded
