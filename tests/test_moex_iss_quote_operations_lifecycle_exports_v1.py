from omni_cio.contracts.v1 import MoexQuoteAlertEvidenceV1
from omni_cio.contracts.v1.moex_alerting import (
    MoexQuoteAlertEvidenceV1 as DirectMoexQuoteAlertEvidenceV1,
)
from omni_cio.observability import (
    MoexQuoteOperationsBatchV1,
    MoexQuoteOperationsLifecycleError,
    MoexQuoteOperationsLifecycleV1,
)
from omni_cio.observability.moex_iss_quote_operations_lifecycle_v1 import (
    MoexQuoteOperationsBatchV1 as DirectMoexQuoteOperationsBatchV1,
)
from omni_cio.observability.moex_iss_quote_operations_lifecycle_v1 import (
    MoexQuoteOperationsLifecycleError as DirectMoexQuoteOperationsLifecycleError,
)
from omni_cio.observability.moex_iss_quote_operations_lifecycle_v1 import (
    MoexQuoteOperationsLifecycleV1 as DirectMoexQuoteOperationsLifecycleV1,
)


def test_moex_operations_evidence_exports_are_stable() -> None:
    assert MoexQuoteAlertEvidenceV1 is DirectMoexQuoteAlertEvidenceV1
    assert MoexQuoteOperationsBatchV1 is DirectMoexQuoteOperationsBatchV1
    assert (
        MoexQuoteOperationsLifecycleError
        is DirectMoexQuoteOperationsLifecycleError
    )
    assert MoexQuoteOperationsLifecycleV1 is DirectMoexQuoteOperationsLifecycleV1
