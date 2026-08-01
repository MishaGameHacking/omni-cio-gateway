from omni_cio.contracts.v1.expert_ra_alerting import (
    ExpertRaRatingActionsAlertEvidenceV1,
)
from omni_cio.observability import (
    ExpertRaRatingActionsOperationsBatchV1,
    ExpertRaRatingActionsOperationsLifecycleError,
    ExpertRaRatingActionsOperationsLifecycleV1,
)


def test_expert_ra_operations_evidence_symbols_are_stable() -> None:
    assert ExpertRaRatingActionsAlertEvidenceV1.__name__.endswith("V1")
    assert ExpertRaRatingActionsOperationsBatchV1.__name__.endswith("V1")
    assert ExpertRaRatingActionsOperationsLifecycleV1.__name__.endswith("V1")
    assert issubclass(ExpertRaRatingActionsOperationsLifecycleError, ValueError)
