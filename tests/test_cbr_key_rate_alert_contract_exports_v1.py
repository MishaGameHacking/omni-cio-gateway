from __future__ import annotations

from omni_cio.contracts import v1
from omni_cio.contracts.v1.alerting import (
    CbrKeyRateAlertDisposition,
    CbrKeyRateAlertEvidenceV1,
    CbrKeyRateAlertEvaluationV1,
    CbrKeyRateAlertKind,
    CbrKeyRateAlertPolicyV1,
)


def test_alerting_contracts_are_exported_from_v1_package() -> None:
    assert v1.CbrKeyRateAlertDisposition is CbrKeyRateAlertDisposition
    assert v1.CbrKeyRateAlertEvidenceV1 is CbrKeyRateAlertEvidenceV1
    assert v1.CbrKeyRateAlertEvaluationV1 is CbrKeyRateAlertEvaluationV1
    assert v1.CbrKeyRateAlertKind is CbrKeyRateAlertKind
    assert v1.CbrKeyRateAlertPolicyV1 is CbrKeyRateAlertPolicyV1
