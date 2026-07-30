from omni_cio.contracts.v1 import (
    MoexQuoteAlertDisposition,
    MoexQuoteAlertEvaluationV1,
    MoexQuoteAlertKind,
    MoexQuoteAlertPolicyV1,
)
from omni_cio.contracts.v1.moex_alerting import (
    MoexQuoteAlertDisposition as DirectMoexQuoteAlertDisposition,
)
from omni_cio.contracts.v1.moex_alerting import (
    MoexQuoteAlertEvaluationV1 as DirectMoexQuoteAlertEvaluationV1,
)
from omni_cio.contracts.v1.moex_alerting import (
    MoexQuoteAlertKind as DirectMoexQuoteAlertKind,
)
from omni_cio.contracts.v1.moex_alerting import (
    MoexQuoteAlertPolicyV1 as DirectMoexQuoteAlertPolicyV1,
)
from omni_cio.observability import (
    MoexQuoteAlertPolicyError,
    MoexQuoteAlertPolicyEvaluatorV1,
)
from omni_cio.observability.moex_iss_quote_alert_policy_v1 import (
    MoexQuoteAlertPolicyError as DirectMoexQuoteAlertPolicyError,
)
from omni_cio.observability.moex_iss_quote_alert_policy_v1 import (
    MoexQuoteAlertPolicyEvaluatorV1 as DirectMoexQuoteAlertPolicyEvaluatorV1,
)


def test_global_moex_alert_exports_are_stable() -> None:
    assert MoexQuoteAlertDisposition is DirectMoexQuoteAlertDisposition
    assert MoexQuoteAlertEvaluationV1 is DirectMoexQuoteAlertEvaluationV1
    assert MoexQuoteAlertKind is DirectMoexQuoteAlertKind
    assert MoexQuoteAlertPolicyV1 is DirectMoexQuoteAlertPolicyV1
    assert MoexQuoteAlertPolicyError is DirectMoexQuoteAlertPolicyError
    assert MoexQuoteAlertPolicyEvaluatorV1 is DirectMoexQuoteAlertPolicyEvaluatorV1
