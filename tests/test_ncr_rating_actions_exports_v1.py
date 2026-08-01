from omni_cio.contracts.v1 import (
    NcrIssuerRatingActionsSnapshotV1,
    NcrIssuerRatingActionV1,
)
from omni_cio.contracts.v1.ncr_ratings import (
    NcrIssuerRatingActionsSnapshotV1 as DirectSnapshotV1,
)
from omni_cio.contracts.v1.ncr_ratings import (
    NcrIssuerRatingActionV1 as DirectActionV1,
)
from omni_cio.market import (
    NCR_RATING_ACTIONS_ENDPOINT,
    NCR_RATING_ACTIONS_SOURCE_ID,
    NcrRatingActionsSourceError,
    fetch_ncr_issuer_rating_actions,
    parse_ncr_issuer_rating_actions_html,
)


def test_ncr_contract_and_source_symbols_are_stable() -> None:
    assert NcrIssuerRatingActionV1 is DirectActionV1
    assert NcrIssuerRatingActionsSnapshotV1 is DirectSnapshotV1
    assert NcrIssuerRatingActionV1.__name__.endswith("V1")
    assert NcrIssuerRatingActionsSnapshotV1.__name__.endswith("V1")
    assert NCR_RATING_ACTIONS_ENDPOINT == ("https://ratings.ru/ratings/press-releases/")
    assert NCR_RATING_ACTIONS_SOURCE_ID == ("NCR.press_releases.issuer_rating_actions")
    assert issubclass(NcrRatingActionsSourceError, ValueError)
    assert callable(fetch_ncr_issuer_rating_actions)
    assert callable(parse_ncr_issuer_rating_actions_html)
