"""Offline shadow evaluation for paper scenarios."""

from omni_cio.shadow.evaluator_v1 import (
    ShadowEvaluationError,
    evaluate_paper_purchase,
)
from omni_cio.shadow.series_v1 import (
    ShadowSeriesEvaluationError,
    evaluate_paper_purchase_series,
)

__all__ = [
    "ShadowEvaluationError",
    "ShadowSeriesEvaluationError",
    "evaluate_paper_purchase",
    "evaluate_paper_purchase_series",
]
