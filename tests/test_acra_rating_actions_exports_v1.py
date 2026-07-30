from omni_cio.contracts.v1 import (
    AcraIssuerRatingActionsSnapshotV1,
    AcraIssuerRatingActionV1,
    CreditRatingOutlook,
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)
from omni_cio.contracts.v1.ratings import (
    AcraIssuerRatingActionsSnapshotV1 as DirectSnapshot,
)
from omni_cio.contracts.v1.ratings import (
    AcraIssuerRatingActionV1 as DirectRecord,
)
from omni_cio.contracts.v1.ratings import (
    CreditRatingOutlook as DirectOutlook,
)
from omni_cio.contracts.v1.ratings import (
    CreditRatingSourceErrorCode as DirectErrorCode,
)
from omni_cio.contracts.v1.ratings import (
    CreditRatingSourceStatus as DirectStatus,
)
from omni_cio.market import (
    ACRA_RATING_ACTIONS_ENDPOINT,
    ACRA_RATING_ACTIONS_SOURCE_ID,
    AcraRatingActionsSourceError,
    fetch_acra_issuer_rating_actions,
    parse_acra_issuer_rating_actions_html,
)
from omni_cio.market.acra_rating_actions_v1 import (
    ACRA_RATING_ACTIONS_ENDPOINT as DirectEndpoint,
)
from omni_cio.market.acra_rating_actions_v1 import (
    ACRA_RATING_ACTIONS_SOURCE_ID as DirectSourceId,
)
from omni_cio.market.acra_rating_actions_v1 import (
    AcraRatingActionsSourceError as DirectSourceError,
)
from omni_cio.market.acra_rating_actions_v1 import (
    fetch_acra_issuer_rating_actions as DirectFetch,
)
from omni_cio.market.acra_rating_actions_v1 import (
    parse_acra_issuer_rating_actions_html as DirectParse,
)


def test_acra_rating_contract_exports_are_stable() -> None:
    assert AcraIssuerRatingActionsSnapshotV1 is DirectSnapshot
    assert AcraIssuerRatingActionV1 is DirectRecord
    assert CreditRatingOutlook is DirectOutlook
    assert CreditRatingSourceErrorCode is DirectErrorCode
    assert CreditRatingSourceStatus is DirectStatus


def test_acra_rating_source_exports_are_stable() -> None:
    assert ACRA_RATING_ACTIONS_ENDPOINT == DirectEndpoint
    assert ACRA_RATING_ACTIONS_SOURCE_ID == DirectSourceId
    assert AcraRatingActionsSourceError is DirectSourceError
    assert fetch_acra_issuer_rating_actions is DirectFetch
    assert parse_acra_issuer_rating_actions_html is DirectParse
