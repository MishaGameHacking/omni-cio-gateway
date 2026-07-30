from __future__ import annotations

from omni_cio.contracts.v1 import (
    MoexIssQuoteErrorCode,
    MoexIssQuoteStatus,
    MoexIssTqbrQuoteSnapshotV1,
)
from omni_cio.market import (
    MOEX_ISS_TQBR_QUOTE_ENDPOINT_TEMPLATE,
    MoexIssQuoteSourceError,
    build_moex_iss_tqbr_quote_url,
    fetch_moex_iss_tqbr_quote,
    parse_moex_iss_tqbr_quote_json,
)


def test_moex_quote_contracts_are_exported_from_versioned_package() -> None:
    assert MoexIssQuoteStatus.AVAILABLE.value == "available"
    assert MoexIssQuoteErrorCode.EMPTY.value == "MOEX_ISS_QUOTE_EMPTY"
    assert MoexIssTqbrQuoteSnapshotV1.__name__ == "MoexIssTqbrQuoteSnapshotV1"


def test_moex_quote_source_is_exported_from_market_package() -> None:
    assert MOEX_ISS_TQBR_QUOTE_ENDPOINT_TEMPLATE.startswith(
        "https://iss.moex.com/"
    )
    assert MoexIssQuoteSourceError.__name__ == "MoexIssQuoteSourceError"
    assert callable(build_moex_iss_tqbr_quote_url)
    assert callable(fetch_moex_iss_tqbr_quote)
    assert callable(parse_moex_iss_tqbr_quote_json)
