from __future__ import annotations

from scripts.check_gpt_configuration_consistency import (
    CANONICAL_INSTRUCTIONS,
    CANONICAL_UI_NAME,
    KNOWLEDGE_FILES,
    V9_PROGRAM,
    validate,
)


def test_gpt_configuration_consistency() -> None:
    assert validate() == []


def test_canonical_release_contract_is_explicit() -> None:
    assert CANONICAL_UI_NAME.endswith("v8.6.1")
    assert CANONICAL_INSTRUCTIONS.endswith("V8_6_1_COMPACT.txt")
    assert V9_PROGRAM.endswith("OMNI_CIO_V9_PORTFOLIO_AUTOPILOT_PROGRAM.md")
    assert len(KNOWLEDGE_FILES) == 10
    assert len(set(KNOWLEDGE_FILES)) == 10
