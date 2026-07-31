from omni_cio.contracts.v1.acra_alerting import (
    AcraRatingActionsAlertDisposition,
    AcraRatingActionsAlertEvaluationV1,
    AcraRatingActionsAlertKind,
    AcraRatingActionsAlertPolicyV1,
)
from omni_cio.observability.acra_rating_actions_alert_policy_v1 import (
    AcraRatingActionsAlertPolicyError,
    AcraRatingActionsAlertPolicyEvaluatorV1,
)


def test_acra_alert_contract_and_runtime_symbols_are_stable() -> None:
    assert AcraRatingActionsAlertDisposition.FIRED.value == "fired"
    assert AcraRatingActionsAlertKind.SOURCE_UNAVAILABLE.value == "source_unavailable"
    assert AcraRatingActionsAlertPolicyV1.__name__.endswith("V1")
    assert AcraRatingActionsAlertEvaluationV1.__name__.endswith("V1")
    assert AcraRatingActionsAlertPolicyEvaluatorV1.__name__.endswith("V1")
    assert issubclass(AcraRatingActionsAlertPolicyError, ValueError)
