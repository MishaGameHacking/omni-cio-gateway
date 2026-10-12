from __future__ import annotations

import unittest

from backend.ai_policy import (
    AnalysisBudget,
    AnalysisReason,
    AnalysisSignals,
    AnalysisTier,
    decide_analysis,
)


class AiPolicyTests(unittest.TestCase):
    def test_no_change_spends_no_tokens(self) -> None:
        decision = decide_analysis(
            AnalysisSignals(),
            AnalysisBudget(10, 4, 1),
        )
        self.assertEqual(decision.tier, AnalysisTier.NONE)
        self.assertFalse(decision.notify_user)
        self.assertEqual(decision.max_output_tokens, 0)

    def test_morning_brief_is_deduplicated_when_digest_is_unchanged(self) -> None:
        decision = decide_analysis(
            AnalysisSignals(morning_due=True, digest_changed=False),
            AnalysisBudget(10, 4, 1),
        )
        self.assertEqual(decision.tier, AnalysisTier.NONE)

    def test_portfolio_trade_uses_standard_tier(self) -> None:
        decision = decide_analysis(
            AnalysisSignals(portfolio_changed=True, digest_changed=True),
            AnalysisBudget(10, 4, 1),
        )
        self.assertEqual(decision.tier, AnalysisTier.STANDARD)
        self.assertEqual(decision.reason, AnalysisReason.PORTFOLIO_CHANGED)

    def test_critical_risk_escalates_and_bypasses_cooldown(self) -> None:
        decision = decide_analysis(
            AnalysisSignals(critical_risk=True, minutes_since_last_analysis=2),
            AnalysisBudget(10, 4, 1),
        )
        self.assertEqual(decision.tier, AnalysisTier.PREMIUM)
        self.assertEqual(decision.reason, AnalysisReason.RISK_EVENT)
        self.assertTrue(decision.notify_user)

    def test_expensive_tier_downgrades_instead_of_exceeding_budget(self) -> None:
        decision = decide_analysis(
            AnalysisSignals(critical_risk=True),
            AnalysisBudget(fast_calls_left=2, standard_calls_left=1, premium_calls_left=0),
        )
        self.assertEqual(decision.tier, AnalysisTier.STANDARD)

    def test_budget_exhaustion_blocks_analysis(self) -> None:
        decision = decide_analysis(
            AnalysisSignals(cash_changed=True, digest_changed=True),
            AnalysisBudget(0, 0, 0),
        )
        self.assertEqual(decision.tier, AnalysisTier.NONE)
        self.assertEqual(decision.reason, AnalysisReason.BUDGET_EXHAUSTED)


if __name__ == "__main__":
    unittest.main()
