from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STYLE_FILE = ROOT / "gpt" / "knowledge" / "13_COMMUNICATION_STYLE_2026.txt"


def _style_text() -> str:
    return STYLE_FILE.read_text(encoding="utf-8")


def test_simple_fact_mode_stays_compact() -> None:
    text = _style_text()

    assert "1. SIMPLE FACT" in text
    assert "3-8 essential facts" in text
    assert "Do not append a full risk vector" in text
    assert "do not turn every request into a full investment report" in text.lower()


def test_portfolio_management_puts_decision_first() -> None:
    text = _style_text()

    assert "3. PORTFOLIO MANAGEMENT" in text
    assert "A. MAIN DECISION" in text
    assert "F. NEXT TRIGGER" in text
    assert "simple cash-only portfolio" in text


def test_exact_action_mode_remains_isolated() -> None:
    text = _style_text()

    assert "2. EXACT ACTION / TECHNICAL" in text
    assert "call only the requested Action" in text
    assert "do not add investment recommendations" in text


def test_style_preserves_read_only_invariant() -> None:
    text = _style_text()

    assert "Keep `trading_methods=false`" in text
    assert "never imply that an order was placed" in text
