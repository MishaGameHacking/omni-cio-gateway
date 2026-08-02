from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = ROOT / "gpt" / "knowledge" / "10_DECISION_ENGINE_AND_CANDIDATE_COMPARISON.txt"


def _knowledge_text() -> str:
    return KNOWLEDGE_FILE.read_text(encoding="utf-8")


def test_candidate_ranking_knowledge_keeps_mandatory_funnel() -> None:
    text = _knowledge_text()
    required_markers = (
        "Candidate Funnel",
        "PORTFOLIO GATE",
        "ROLE GATE",
        "SHORTLIST",
        "IDENTITY GATE",
        "MARKET GATE",
        "AFFORDABILITY GATE",
        "COMPARISON GATE",
        "DECISION GATE",
        "NO_ACTION / CASH",
        "getPurchaseCapacityPreview",
    )

    missing = [marker for marker in required_markers if marker not in text]
    assert missing == []


def test_candidate_ranking_blocks_stale_or_unverified_exact_sizing() -> None:
    text = _knowledge_text()

    assert "старый last price не считать текущей ценой исполнения" in text
    assert "withdrawal limit не считать buying power" in text
    assert "hard blocker не усреднять" in text
    assert "точная покупательная способность не подтверждена" in text
    assert "BLOCKED не означает «плохой актив вообще»" in text


def test_candidate_ranking_preserves_read_only_contract() -> None:
    text = _knowledge_text()

    assert "Он не создаёт, не отправляет, не заменяет и не отменяет заявки." in text
    assert "`trading_methods=false` остаётся обязательным инвариантом." in text
