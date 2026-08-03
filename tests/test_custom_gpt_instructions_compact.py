from pathlib import Path


INSTRUCTIONS = Path("gpt/CUSTOM_GPT_INSTRUCTIONS_V8_6_1_COMPACT.txt")


def test_compact_instructions_fit_gpt_editor_limit_with_headroom() -> None:
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    assert len(text) <= 7_900


def test_compact_instructions_preserve_execution_safety_invariants() -> None:
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    required_fragments = (
        "REAL READ-ONLY",
        "REAL EXECUTION",
        "SANDBOX",
        "getRealTradingStatus",
        "prepareRealTrade",
        "executeRealTrade",
        "getRealOrderState",
        "Реальная заявка ещё не отправлена",
        "confirmation_phrase",
        "unknown_do_not_resubmit",
        "MARKET/BESTPRICE",
        "margin/uncovered/short",
        "REAL_TRADING_ENABLED",
        "getSandboxTradingStatus",
        "prepareSandboxTrade",
        "executeSandboxTrade",
        "getSandboxOrderState",
        "EXECUTION_REPORT_STATUS_FILL",
    )
    missing = [fragment for fragment in required_fragments if fragment not in text]
    assert not missing, f"Missing safety-critical fragments: {missing}"


def test_compact_instructions_keep_portfolio_dispatch_contract() -> None:
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    snapshot = text.index("getPortfolioSnapshot")
    liquidity = text.index("getCashLiquiditySnapshot", snapshot)
    analytics = text.index("getPortfolioAnalytics", liquidity)
    assert snapshot < liquidity < analytics
