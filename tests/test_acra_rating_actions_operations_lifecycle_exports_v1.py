from omni_cio.contracts.v1.acra_alerting import (
    AcraRatingActionsAlertEvidenceV1,
)
from omni_cio.observability import (
    AcraRatingActionsOperationsBatchV1,
    AcraRatingActionsOperationsLifecycleError,
    AcraRatingActionsOperationsLifecycleV1,
)


def test_acra_operations_evidence_symbols_are_stable() -> None:
    assert AcraRatingActionsAlertEvidenceV1.__name__.endswith("V1")
    assert AcraRatingActionsOperationsBatchV1.__name__.endswith("V1")
    assert AcraRatingActionsOperationsLifecycleV1.__name__.endswith("V1")
    assert issubclass(AcraRatingActionsOperationsLifecycleError, ValueError)
