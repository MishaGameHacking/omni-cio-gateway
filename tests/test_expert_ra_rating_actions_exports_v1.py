from omni_cio.contracts.v1 import (
    ExpertRaIssuerRatingActionsSnapshotV1,
    ExpertRaIssuerRatingActionV1,
)
from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsSnapshotV1 as DirectSnapshotV1,
)
from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionV1 as DirectActionV1,
)
from omni_cio.market import (
    EXPERT_RA_RATING_ACTIONS_ENDPOINT,
    EXPERT_RA_RATING_ACTIONS_SOURCE_ID,
    ExpertRaRatingActionsSourceError,
    fetch_expert_ra_issuer_rating_actions,
    parse_expert_ra_issuer_rating_actions_html,
)


def test_expert_ra_contract_and_source_symbols_are_stable() -> None:
    assert ExpertRaIssuerRatingActionV1 is DirectActionV1
    assert ExpertRaIssuerRatingActionsSnapshotV1 is DirectSnapshotV1
    assert ExpertRaIssuerRatingActionV1.__name__.endswith("V1")
    assert ExpertRaIssuerRatingActionsSnapshotV1.__name__.endswith("V1")
    assert EXPERT_RA_RATING_ACTIONS_ENDPOINT == "https://raexpert.ru/"
    assert EXPERT_RA_RATING_ACTIONS_SOURCE_ID == "EXPERT_RA.home.rating_actions"
    assert issubclass(ExpertRaRatingActionsSourceError, ValueError)
    assert callable(fetch_expert_ra_issuer_rating_actions)
    assert callable(parse_expert_ra_issuer_rating_actions_html)
