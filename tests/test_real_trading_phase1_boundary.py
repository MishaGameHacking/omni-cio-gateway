from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REAL_ROOT = ROOT / "omni_cio" / "real_trading"


def test_phase1_real_trading_is_not_registered_in_gateway() -> None:
    runtime_files = [
        ROOT / "app.py",
        ROOT / "app_v371.py",
        ROOT / "app_v360.py",
        ROOT / "main.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in runtime_files)
    assert "omni_cio.real_trading" not in combined
    assert "register_real_trading" not in combined
    assert not (REAL_ROOT / "routes_v1.py").exists()


def test_phase1_client_is_hard_bound_and_has_no_readonly_token_fallback() -> None:
    source = (REAL_ROOT / "client_v1.py").read_text(encoding="utf-8")
    assert 'REAL_REST_BASE_URL = "https://invest-public-api.tbank.ru/rest"' in source
    assert "TINVEST_TOKEN" not in source
    assert "TINVEST_SANDBOX_TOKEN" not in source
    assert "sandbox-invest-public-api.tbank.ru" not in source


def test_phase1_write_allowlist_is_deliberately_narrow() -> None:
    source = (REAL_ROOT / "client_v1.py").read_text(encoding="utf-8")
    assert '"PostOrder": ORDERS_SERVICE' in source
    for forbidden in (
        '"ReplaceOrder"',
        '"PostOrderAsync"',
        '"CancelOrder"',
        "StopOrdersService",
        "Withdraw",
        "Transfer",
    ):
        assert forbidden not in source


def test_phase1_submit_hard_disables_margin() -> None:
    source = (REAL_ROOT / "service_v1.py").read_text(encoding="utf-8")
    assert '"orderType": "ORDER_TYPE_LIMIT"' in source
    assert '"timeInForce": "TIME_IN_FORCE_DAY"' in source
    assert '"priceType": "PRICE_TYPE_CURRENCY"' in source
    assert '"confirmMarginTrade": False' in source


def test_phase1_production_construction_requires_durable_journal() -> None:
    source = (REAL_ROOT / "service_v1.py").read_text(encoding="utf-8")
    assert "require_durable_journal: bool = True" in source
    assert "REAL_DURABLE_JOURNAL_REQUIRED" in source
    journal_source = (REAL_ROOT / "journal_v1.py").read_text(encoding="utf-8")
    assert "class InMemoryRealExecutionJournalV1" in journal_source
    assert "durable = False" in journal_source
