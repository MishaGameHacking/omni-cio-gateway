from omni_cio.contracts.v1.expert_ra_alerting import (
    ExpertRaRatingActionsAlertEvidenceV1 as DirectEvidence,
)
from omni_cio.observability import (
    ExpertRaRatingActionsAlertEvidenceV1,
    ExpertRaRatingActionsOperationsBatchV1,
    ExpertRaRatingActionsOperationsLifecycleError,
    ExpertRaRatingActionsOperationsLifecycleV1,
)
from omni_cio.observability.expert_ra_rating_actions_operations_lifecycle_v1 import (
    ExpertRaRatingActionsOperationsBatchV1 as DirectBatch,
)
from omni_cio.observability.expert_ra_rating_actions_operations_lifecycle_v1 import (
    ExpertRaRatingActionsOperationsLifecycleError as DirectError,
)
from omni_cio.observability.expert_ra_rating_actions_operations_lifecycle_v1 import (
    ExpertRaRatingActionsOperationsLifecycleV1 as DirectLifecycle,
)


def test_expert_ra_operations_contract_export_is_stable() -> None:
    assert ExpertRaRatingActionsAlertEvidenceV1 is DirectEvidence


def test_expert_ra_operations_runtime_exports_are_stable() -> None:
    assert ExpertRaRatingActionsOperationsBatchV1 is DirectBatch
    assert ExpertRaRatingActionsOperationsLifecycleError is DirectError
    assert ExpertRaRatingActionsOperationsLifecycleV1 is DirectLifecycle
