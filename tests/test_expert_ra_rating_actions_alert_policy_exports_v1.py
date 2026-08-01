from omni_cio.contracts.v1.expert_ra_alerting import (
    ExpertRaRatingActionsAlertDisposition as DirectDisposition,
)
from omni_cio.contracts.v1.expert_ra_alerting import (
    ExpertRaRatingActionsAlertEvaluationV1 as DirectEvaluation,
)
from omni_cio.contracts.v1.expert_ra_alerting import (
    ExpertRaRatingActionsAlertKind as DirectKind,
)
from omni_cio.contracts.v1.expert_ra_alerting import (
    ExpertRaRatingActionsAlertPolicyV1 as DirectPolicy,
)
from omni_cio.observability import (
    ExpertRaRatingActionsAlertDisposition,
    ExpertRaRatingActionsAlertEvaluationV1,
    ExpertRaRatingActionsAlertKind,
    ExpertRaRatingActionsAlertPolicyError,
    ExpertRaRatingActionsAlertPolicyEvaluatorV1,
    ExpertRaRatingActionsAlertPolicyV1,
)
from omni_cio.observability.expert_ra_rating_actions_alert_policy_v1 import (
    ExpertRaRatingActionsAlertPolicyError as DirectPolicyError,
)
from omni_cio.observability.expert_ra_rating_actions_alert_policy_v1 import (
    ExpertRaRatingActionsAlertPolicyEvaluatorV1 as DirectEvaluator,
)


def test_expert_ra_alert_contract_exports_are_stable() -> None:
    assert ExpertRaRatingActionsAlertDisposition is DirectDisposition
    assert ExpertRaRatingActionsAlertEvaluationV1 is DirectEvaluation
    assert ExpertRaRatingActionsAlertKind is DirectKind
    assert ExpertRaRatingActionsAlertPolicyV1 is DirectPolicy


def test_expert_ra_alert_runtime_exports_are_stable() -> None:
    assert ExpertRaRatingActionsAlertPolicyError is DirectPolicyError
    assert ExpertRaRatingActionsAlertPolicyEvaluatorV1 is DirectEvaluator
