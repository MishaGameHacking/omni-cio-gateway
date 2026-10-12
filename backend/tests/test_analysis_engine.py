from __future__ import annotations

import unittest

from backend.ai_policy import AnalysisBudget, AnalysisReason, AnalysisSignals, AnalysisTier
from backend.analysis_engine import (
    AnalysisValidationError,
    analyze_if_needed,
)
from backend.timeweb_ai import TimewebAIResult, TimewebAIUsage


class FakeGateway:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def complete_json(self, **kwargs) -> TimewebAIResult:
        self.calls.append(kwargs)
        return TimewebAIResult(
            model="test/model",
            data=self.payload,
            usage=TimewebAIUsage(100, 30, 130),
        )


def valid_report(*, severity: str = "info") -> dict:
    return {
        "severity": severity,
        "headline": "Портфель без существенных изменений",
        "summary": "Проверенные показатели находятся в заданных пределах.",
        "actions": ["Продолжить наблюдение до вечернего среза"],
        "evidence": [
            {
                "fact": "Доля крупнейшей позиции — 18%",
                "source_id": "portfolio:snapshot:42",
                "as_of": "2026-10-12T09:00:00+03:00",
            }
        ],
        "uncertainties": [],
        "valid_until": "2026-10-12T18:45:00+03:00",
    }


class AnalysisEngineTests(unittest.TestCase):
    def test_no_material_change_never_calls_gateway(self) -> None:
        gateway = FakeGateway(valid_report())
        result = analyze_if_needed(
            signals=AnalysisSignals(),
            budget=AnalysisBudget(5, 2, 1),
            context={"portfolio": {"total": 1000}},
            client=gateway,  # type: ignore[arg-type]
        )
        self.assertEqual(result.decision.tier, AnalysisTier.NONE)
        self.assertIsNone(result.report)
        self.assertEqual(gateway.calls, [])

    def test_morning_digest_uses_standard_tier_and_structured_context(self) -> None:
        gateway = FakeGateway(valid_report())
        result = analyze_if_needed(
            signals=AnalysisSignals(morning_due=True, digest_changed=True),
            budget=AnalysisBudget(5, 2, 1),
            context={
                "portfolio": {"total": 1000, "currency": "RUB"},
                "sources": [{"id": "portfolio:snapshot:42", "fresh": True}],
            },
            client=gateway,  # type: ignore[arg-type]
        )
        self.assertEqual(result.decision.tier, AnalysisTier.STANDARD)
        self.assertEqual(result.decision.reason, AnalysisReason.MORNING_BRIEF)
        self.assertEqual(result.model, "test/model")
        self.assertEqual(result.usage.total_tokens, 130)
        self.assertEqual(result.report.severity, "info")
        self.assertEqual(len(gateway.calls), 1)
        self.assertEqual(gateway.calls[0]["tier"], AnalysisTier.STANDARD)
        self.assertEqual(gateway.calls[0]["max_output_tokens"], 750)

    def test_critical_rule_cannot_be_downgraded_to_info_by_model(self) -> None:
        gateway = FakeGateway(valid_report(severity="info"))
        result = analyze_if_needed(
            signals=AnalysisSignals(critical_risk=True, digest_changed=True),
            budget=AnalysisBudget(5, 2, 1),
            context={"risk": {"margin_call_distance_percent": 2.0}},
            client=gateway,  # type: ignore[arg-type]
        )
        self.assertEqual(result.decision.tier, AnalysisTier.PREMIUM)
        self.assertEqual(result.report.severity, "critical")
        self.assertTrue(result.decision.notify_user)

    def test_invalid_unverifiable_evidence_is_rejected(self) -> None:
        payload = valid_report()
        payload["evidence"] = [{"fact": "Цена упала"}]
        gateway = FakeGateway(payload)
        with self.assertRaises(AnalysisValidationError):
            analyze_if_needed(
                signals=AnalysisSignals(portfolio_changed=True, digest_changed=True),
                budget=AnalysisBudget(5, 2, 1),
                context={"portfolio": {"changed": True}},
                client=gateway,  # type: ignore[arg-type]
            )

    def test_context_size_is_bounded_before_gateway_call(self) -> None:
        gateway = FakeGateway(valid_report())
        with self.assertRaises(AnalysisValidationError) as raised:
            analyze_if_needed(
                signals=AnalysisSignals(portfolio_changed=True, digest_changed=True),
                budget=AnalysisBudget(5, 2, 1),
                context={"oversized": "x" * 100_000},
                client=gateway,  # type: ignore[arg-type]
            )
        self.assertEqual(str(raised.exception), "analysis_context_too_large")
        self.assertEqual(gateway.calls, [])


if __name__ == "__main__":
    unittest.main()
