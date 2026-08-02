from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
import pytest

from omni_cio.real_trading import routes_v1


def fake_base() -> SimpleNamespace:
    return SimpleNamespace(require_gateway_key=lambda: None, CAPABILITIES=[])


def operation_ids(app: FastAPI) -> set[str]:
    schema = app.openapi()
    result: set[str] = set()
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if isinstance(operation, dict) and operation.get("operationId"):
                result.add(str(operation["operationId"]))
    return result


def enable_static_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REAL_TRADING_ENABLED", "true")
    monkeypatch.setenv(
        "TINVEST_TRADING_TOKEN",
        "unit-test-trading-value",  # pragma: allowlist secret
    )
    monkeypatch.setenv(
        "GATEWAY_API_KEY",
        "unit-test-gateway-value",  # pragma: allowlist secret
    )
    monkeypatch.setenv("REAL_TRADING_MAX_ORDER_RUB", "1000")
    monkeypatch.setenv("REAL_TRADING_MAX_DAILY_RUB", "2000")


def test_flag_off_publishes_no_real_action(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REAL_TRADING_ENABLED", raising=False)
    app = FastAPI()
    registered = routes_v1.maybe_register_real_trading_gateway(
        app=app,
        base=fake_base(),
        app_version="test",
        expected_account_id_provider=lambda: "account",
        market_snapshot_provider=lambda instrument_uid: {"instrument_uid": instrument_uid},
    )
    assert registered is False
    assert not any(name.startswith(("getReal", "prepareReal", "executeReal")) for name in operation_ids(app))


def test_invalid_static_config_publishes_status_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("REAL_TRADING_ENABLED", "true")
    monkeypatch.delenv("TINVEST_TRADING_TOKEN", raising=False)
    monkeypatch.setenv(
        "GATEWAY_API_KEY",
        "unit-test-gateway-value",  # pragma: allowlist secret
    )
    monkeypatch.setenv("REAL_TRADING_MAX_ORDER_RUB", "1000")
    monkeypatch.setenv("REAL_TRADING_MAX_DAILY_RUB", "2000")
    app = FastAPI()
    registered = routes_v1.maybe_register_real_trading_gateway(
        app=app,
        base=fake_base(),
        app_version="test",
        expected_account_id_provider=lambda: "account",
        market_snapshot_provider=lambda instrument_uid: {"instrument_uid": instrument_uid},
        journal_path=tmp_path / "real.sqlite3",
    )
    ids = operation_ids(app)
    assert registered is False
    assert "getRealTradingStatus" in ids
    assert "prepareRealTrade" not in ids
    assert "executeRealTrade" not in ids
    assert "getRealOrderState" not in ids


def test_valid_static_config_publishes_narrow_surface(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    enable_static_config(monkeypatch)
    app = FastAPI()
    base = fake_base()
    registered = routes_v1.maybe_register_real_trading_gateway(
        app=app,
        base=base,
        app_version="test",
        expected_account_id_provider=lambda: "account",
        market_snapshot_provider=lambda instrument_uid: {"instrument_uid": instrument_uid},
        journal_path=tmp_path / "real.sqlite3",
    )
    ids = operation_ids(app)
    assert registered is True
    assert {
        "getRealTradingStatus",
        "prepareRealTrade",
        "executeRealTrade",
        "getRealOrderState",
    }.issubset(ids)
    assert "cancelRealOrder" not in ids
    assert "replaceRealOrder" not in ids
    assert "real_trading_v1" in base.CAPABILITIES

    execute = app.openapi()["paths"]["/real-trading/trade/execute"]["post"]
    assert execute["x-openai-isConsequential"] is True


def test_active_production_app_keeps_real_actions_absent_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REAL_TRADING_ENABLED", raising=False)
    # Import after the environment is explicitly default-off. The gateway's
    # registration hook must therefore leave all real-money operations absent.
    import app as production_app

    ids = operation_ids(production_app.app)
    assert "getRealTradingStatus" not in ids
    assert "prepareRealTrade" not in ids
    assert "executeRealTrade" not in ids
    assert "getRealOrderState" not in ids
