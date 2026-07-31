from omni_cio.contracts.v1.acra_alerting import (
    AcraRatingActionsAlertDisposition,
    AcraRatingActionsAlertEvaluationV1,
    AcraRatingActionsAlertKind,
    AcraRatingActionsAlertPolicyV1,
)
from omni_cio.observability import (
    AcraRatingActionsAlertPolicyError,
    AcraRatingActionsAlertPolicyEvaluatorV1,
)
from omni_cio.observability.acra_rating_actions_alert_policy_v1 import (
    AcraRatingActionsAlertPolicyError as DirectPolicyError,
)
from omni_cio.observability.acra_rating_actions_alert_policy_v1 import (
    AcraRatingActionsAlertPolicyEvaluatorV1 as DirectPolicyEvaluator,
)


def test_acra_alert_contract_and_observability_exports_are_stable() -> None:
    assert AcraRatingActionsAlertDisposition.FIRED.value == "fired"
    assert AcraRatingActionsAlertKind.SOURCE_UNAVAILABLE.value == (
        "source_unavailable"
    )
    assert AcraRatingActionsAlertPolicyV1().scope == (
        "global_acra_rating_actions_feed"
    )
    assert AcraRatingActionsAlertEvaluationV1.__module__.endswith("acra_alerting")
    assert AcraRatingActionsAlertPolicyError is DirectPolicyError
    assert AcraRatingActionsAlertPolicyEvaluatorV1 is DirectPolicyEvaluator
