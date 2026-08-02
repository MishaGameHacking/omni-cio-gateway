from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
import httpx
import pytest

from omni_cio.sandbox.client_v1 import (
    SANDBOX_REST_BASE_URL,
    SandboxApiFailure,
    SandboxRestClientV1,
)
from omni_cio.sandbox.routes_v1 import (
    maybe_register_sandbox_trading_gateway,
    register_sandbox_trading_gateway,
    test_base,
)
from omni_cio.sandbox.service_v1 import SandboxTradingServiceV1


ACCOUNT_ID = "sandbox-account-1234"
INSTRUMENT_ID = "e6123145-9665-43e0-8413-cd61b8aa9b13"


def _handler_with_counter(counter: dict[str, int]):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "sandbox-invest-public-api.tbank.ru"
        assert request.headers["authorization"] == "Bearer sandbox-test-token"
        method = request.url.path.rsplit("/", 1)[-1]
        counter[method] = counter.get(method, 0) + 1
        if method == "GetSandboxAccounts":
            return httpx.Response(
                200,
                json={
                    "accounts": [
                        {
                            "id": ACCOUNT_ID,
                            "name": "Omni-CIO Sandbox",
                            "status": "ACCOUNT_STATUS_OPEN",
                        }
                    ]
                },
            )
        if method == "GetSandboxMaxLots":
            return httpx.Response(
                200,
                json={"buyLimits": {"buyMaxLots": "10"}},
            )
        if method == "GetSandboxOrderPrice":
            return httpx.Response(
                200,
                json={"totalOrderAmount": {"currency": "rub", "units": "100"}},
            )
        if method == "PostSandboxOrder":
            return httpx.Response(
                200,
                headers={"x-tracking-id": "tracking-test"},
                json={
                    "orderId": "sandbox-exchange-order",
                    "executionReportStatus": "EXECUTION_REPORT_STATUS_NEW",
                },
            )
        if method == "GetSandboxOrderState":
            return httpx.Response(
                200,
                json={"executionReportStatus": "EXECUTION_REPORT_STATUS_FILL"},
            )
        if method == "CancelSandboxOrder":
            return httpx.Response(200, json={"time": "2026-08-02T12:00:00Z"})
        if method == "GetSandboxPortfolio":
            return httpx.Response(200, json={"accountId": ACCOUNT_ID, "positions": []})
        if method == "GetSandboxPositions":
            return httpx.Response(200, json={"accountId": ACCOUNT_ID, "money": []})
        if method == "OpenSandboxAccount":
            return httpx.Response(200, json={"accountId": ACCOUNT_ID})
        if method == "SandboxPayIn":
            return httpx.Response(
                200,
                json={"balance": {"currency": "rub", "units": "100000"}},
            )
        raise AssertionError(f"unexpected sandbox method: {method}")

    return handler


def _service(counter: dict[str, int]) -> SandboxTradingServiceV1:
    client = SandboxRestClientV1(
        "sandbox-test-token",
        transport=httpx.MockTransport(_handler_with_counter(counter)),
    )
    return SandboxTradingServiceV1(
        token="sandbox-test-token",
        gateway_secret="gateway-secret-for-tests",
        client=client,
    )


def test_client_is_hard_bound_to_sandbox_host() -> None:
    counter: dict[str, int] = {}
    service = _service(counter)
    status = service.status()
    assert status["sandbox_host"] == SANDBOX_REST_BASE_URL
    assert status["real_money"] is False
    assert counter == {"GetSandboxAccounts": 1}


def test_prepare_requires_second_explicit_confirmation_and_is_idempotent() -> None:
    counter: dict[str, int] = {}
    service = _service(counter)
    proposal = service.prepare_trade(
        instrument_id=INSTRUMENT_ID,
        direction="BUY",
        quantity_lots=1,
        order_type="LIMIT",
        limit_price="100.25",
        price_type="CURRENCY",
        rationale="Проверка sandbox-контура.",
    )

    assert proposal.state == "prepared"
    assert proposal.confirmation_phrase.startswith("ПОДТВЕРЖДАЮ SANDBOX ")
    assert counter.get("PostSandboxOrder", 0) == 0

    with pytest.raises(SandboxApiFailure) as wrong_confirmation:
        service.execute_trade(proposal.proposal_id, "ПОДТВЕРЖДАЮ SANDBOX WRONG")
    assert wrong_confirmation.value.code == "SANDBOX_CONFIRMATION_MISMATCH"
    assert counter.get("PostSandboxOrder", 0) == 0

    executed, replay = service.execute_trade(
        proposal.proposal_id,
        proposal.confirmation_phrase,
    )
    assert replay is False
    assert executed.state == "executed"
    assert counter["PostSandboxOrder"] == 1

    executed_again, replay_again = service.execute_trade(
        proposal.proposal_id,
        proposal.confirmation_phrase,
    )
    assert replay_again is True
    assert executed_again.order_id == executed.order_id
    assert counter["PostSandboxOrder"] == 1


def test_expired_confirmation_never_submits() -> None:
    counter: dict[str, int] = {}
    service = _service(counter)
    start = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    proposal = service.prepare_trade(
        instrument_id=INSTRUMENT_ID,
        direction="SELL",
        quantity_lots=1,
        order_type="MARKET",
        limit_price=None,
        price_type="CURRENCY",
        rationale="Expiry test",
        now=start,
    )

    with pytest.raises(SandboxApiFailure) as expired:
        service.execute_trade(
            proposal.proposal_id,
            proposal.confirmation_phrase,
            now=start + timedelta(minutes=3),
        )
    assert expired.value.code == "SANDBOX_CONFIRMATION_EXPIRED"
    assert counter.get("PostSandboxOrder", 0) == 0


def test_ambiguous_submission_is_never_automatically_retried() -> None:
    counter: dict[str, int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        counter[method] = counter.get(method, 0) + 1
        if method == "GetSandboxAccounts":
            return httpx.Response(
                200,
                json={
                    "accounts": [
                        {"id": ACCOUNT_ID, "status": "ACCOUNT_STATUS_OPEN"}
                    ]
                },
            )
        if method == "GetSandboxMaxLots":
            return httpx.Response(200, json={"buyLimits": {"buyMaxLots": "10"}})
        if method == "PostSandboxOrder":
            raise httpx.ReadTimeout("response lost", request=request)
        raise AssertionError(method)

    client = SandboxRestClientV1(
        "sandbox-test-token",
        transport=httpx.MockTransport(handler),
    )
    service = SandboxTradingServiceV1(
        token="sandbox-test-token",
        gateway_secret="gateway-secret-for-tests",
        client=client,
    )
    proposal = service.prepare_trade(
        instrument_id=INSTRUMENT_ID,
        direction="BUY",
        quantity_lots=1,
        order_type="MARKET",
        limit_price=None,
        price_type="CURRENCY",
        rationale="Timeout test",
    )

    with pytest.raises(SandboxApiFailure) as ambiguous:
        service.execute_trade(proposal.proposal_id, proposal.confirmation_phrase)
    assert ambiguous.value.ambiguous_submission is True
    assert counter["PostSandboxOrder"] == 1

    with pytest.raises(SandboxApiFailure) as no_retry:
        service.execute_trade(proposal.proposal_id, proposal.confirmation_phrase)
    assert no_retry.value.code == "SANDBOX_ORDER_SUBMISSION_UNCERTAIN"
    assert counter["PostSandboxOrder"] == 1


def test_sandbox_payload_masks_account_id() -> None:
    counter: dict[str, int] = {}
    service = _service(counter)
    payload = service.portfolio()
    assert ACCOUNT_ID not in payload["portfolio_json"]
    assert ACCOUNT_ID not in payload["positions_json"]
    assert "***1234" in payload["portfolio_json"]


def test_registration_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SANDBOX_TRADING_ENABLED", raising=False)
    app = FastAPI()
    registered = maybe_register_sandbox_trading_gateway(
        app=app,
        base=test_base(),
        app_version="test",
    )
    assert registered is False
    assert "/sandbox/trade/execute" not in app.openapi()["paths"]


def test_enabled_openapi_marks_mutations_consequential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SANDBOX_TRADING_ENABLED", "true")
    app = FastAPI()
    register_sandbox_trading_gateway(
        app=app,
        base=test_base(),
        app_version="test",
    )
    schema = app.openapi()
    assert schema["paths"]["/sandbox/trade/execute"]["post"][
        "x-openai-isConsequential"
    ] is True
    assert schema["paths"]["/sandbox/order/cancel"]["post"][
        "x-openai-isConsequential"
    ] is True
    assert schema["paths"]["/sandbox/account/fund"]["post"][
        "x-openai-isConsequential"
    ] is True


def test_source_boundary_contains_no_production_write_endpoint() -> None:
    root = Path(__file__).resolve().parents[1] / "omni_cio" / "sandbox"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(root.glob("*.py"))
    )
    assert "https://invest-public-api.tbank.ru/rest" not in source
    assert "OrdersService/PostOrder" not in source
    assert 'os.environ.get("TINVEST_TOKEN"' not in source
    assert "sandbox-invest-public-api.tbank.ru/rest" in source
    assert "SandboxService" in source
