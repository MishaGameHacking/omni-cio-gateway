from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.ratings import (
    AcraIssuerRatingActionsSnapshotV1,
    AcraIssuerRatingActionV1,
    CreditRatingOutlook,
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)
from omni_cio.market.acra_rating_actions_v1 import (
    ACRA_RATING_ACTIONS_ENDPOINT,
    ACRA_RATING_ACTIONS_SOURCE_ID,
    AcraRatingActionsSourceError,
    fetch_acra_issuer_rating_actions,
    parse_acra_issuer_rating_actions_html,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def _source() -> MarketSourceV1:
    return MarketSourceV1(
        provider="ACRA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id=ACRA_RATING_ACTIONS_SOURCE_ID,
    )


def _page(*items: tuple[str, str, str]) -> bytes:
    cards = "".join(
        (
            '<article class="rating-document">'
            f'<a href="{href}"><span>{title}</span></a>'
            "<div>Corporates</div><div>Press release</div>"
            f"<time>{published_on}</time>"
            "</article>"
        )
        for href, title, published_on in items
    )
    return f"<html><body>{cards}</body></html>".encode()


def test_rating_action_contract_enforces_withdrawn_semantics() -> None:
    record = AcraIssuerRatingActionV1(
        subject_name='Joint-stock company "Bank Dalena"',
        rating="BBB-(RU)",
        action=RatingAction.AFFIRMED,
        outlook=CreditRatingOutlook.STABLE,
        published_on=NOW.date(),
        release_url="https://www.acra-ratings.ru/press-releases/100/?lang=en",
        source=_source(),
    )
    snapshot = AcraIssuerRatingActionsSnapshotV1(
        retrieved_at=NOW,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=_source(),
        records=(record,),
    )
    assert snapshot.records == (record,)
    assert snapshot.trading_methods is False

    with pytest.raises(ValidationError):
        AcraIssuerRatingActionV1(
            subject_name="Issuer",
            rating="A(RU)",
            action=RatingAction.WITHDRAWN,
            published_on=NOW.date(),
            release_url=(
                "https://www.acra-ratings.ru/press-releases/101/?lang=en"
            ),
            source=_source(),
        )


def test_parser_extracts_simple_issuer_actions_and_sorts_newest_first() -> None:
    payload = _page(
        (
            "/press-releases/101/?lang=en",
            'ACRA AFFIRMS BBB-(RU) TO JSC "BANK DALENA", OUTLOOK STABLE',
            "16 Jun 2026",
        ),
        (
            "/press-releases/102/",
            "ACRA UPGRADES EN+ GROUP IPJSC TO AA-(RU), OUTLOOK STABLE",
            "5 Jun 2026",
        ),
        (
            "/press-releases/103/",
            "ACRA WITHDRAWS THE CREDIT RATING OF TEST COMPANY",
            "4 Jun 2026",
        ),
    )

    result = parse_acra_issuer_rating_actions_html(payload, retrieved_at=NOW)

    assert result.status is CreditRatingSourceStatus.AVAILABLE
    assert [record.action for record in result.records] == [
        RatingAction.AFFIRMED,
        RatingAction.UPGRADED,
        RatingAction.WITHDRAWN,
    ]
    assert result.records[0].rating == "BBB-(RU)"
    assert result.records[0].outlook is CreditRatingOutlook.STABLE
    assert result.records[1].subject_name == "EN+ GROUP IPJSC"
    assert result.records[2].rating is None


def test_parser_skips_issue_level_and_non_rating_documents() -> None:
    payload = _page(
        (
            "/press-releases/200/",
            (
                "ACRA ASSIGNS AA+(RU) TO THE SERIES BO-005P-06 "
                "BOND ISSUE OF PJSC MAGNIT"
            ),
            "16 Jun 2026",
        ),
        (
            "/press-releases/201/",
            "ACRA PUBLISHES A METHODOLOGICAL COMMENTARY",
            "15 Jun 2026",
        ),
        (
            "/press-releases/202/",
            "ACRA ASSIGNS A+(RU) TO THE KHABAROVSK KRAI, OUTLOOK STABLE",
            "15 Jun 2026",
        ),
    )

    result = parse_acra_issuer_rating_actions_html(payload, retrieved_at=NOW)

    assert len(result.records) == 1
    assert result.records[0].subject_name == "THE KHABAROVSK KRAI"


def test_parser_skips_unsupported_non_national_and_multi_target_actions() -> None:
    payload = _page(
        (
            "/press-releases/290/",
            "ACRA AFFIRMS BB- TO INTERNATIONAL BANK, OUTLOOK STABLE",
            "16 Jun 2026",
        ),
        (
            "/press-releases/291/",
            (
                "ACRA AFFIRMS AAA(RU) TO FIRST ISSUER AND "
                "AA(RU) TO SECOND ISSUER"
            ),
            "16 Jun 2026",
        ),
        (
            "/press-releases/292/",
            "ACRA AFFIRMS A(RU) TO SUPPORTED ISSUER, OUTLOOK STABLE",
            "16 Jun 2026",
        ),
    )

    result = parse_acra_issuer_rating_actions_html(payload, retrieved_at=NOW)

    assert len(result.records) == 1
    assert result.records[0].subject_name == "SUPPORTED ISSUER"


def test_parser_rejects_unrecognized_issuer_action_shape() -> None:
    payload = _page(
        (
            "/press-releases/300/",
            "ACRA AFFIRMS A(RU) TO",
            "16 Jun 2026",
        ),
    )
    with pytest.raises(
        AcraRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.SCHEMA_INVALID.value,
    ):
        parse_acra_issuer_rating_actions_html(payload, retrieved_at=NOW)


@pytest.mark.parametrize(
    ("href", "expected_code"),
    [
        (
            "https://example.com/press-releases/1/",
            CreditRatingSourceErrorCode.URL_INVALID,
        ),
        (
            "/press-releases/not-a-number/",
            CreditRatingSourceErrorCode.URL_INVALID,
        ),
    ],
)
def test_parser_rejects_release_urls_outside_fixed_scope(
    href: str,
    expected_code: CreditRatingSourceErrorCode,
) -> None:
    payload = _page(
        (
            href,
            "ACRA ASSIGNS A(RU) TO TEST ISSUER, OUTLOOK STABLE",
            "16 Jun 2026",
        ),
    )
    with pytest.raises(AcraRatingActionsSourceError, match=expected_code.value):
        parse_acra_issuer_rating_actions_html(payload, retrieved_at=NOW)


def test_parser_rejects_missing_or_future_publication_date() -> None:
    missing = (
        '<a href="/press-releases/401/">'
        "ACRA ASSIGNS A(RU) TO TEST ISSUER, OUTLOOK STABLE"
        "</a>"
    ).encode()
    with pytest.raises(
        AcraRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value,
    ):
        parse_acra_issuer_rating_actions_html(missing, retrieved_at=NOW)

    future = _page(
        (
            "/press-releases/402/",
            "ACRA ASSIGNS A(RU) TO TEST ISSUER, OUTLOOK STABLE",
            "2 Aug 2026",
        ),
    )
    with pytest.raises(
        AcraRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value,
    ):
        parse_acra_issuer_rating_actions_html(future, retrieved_at=NOW)


def test_parser_rejects_conflicting_duplicate_release() -> None:
    payload = _page(
        (
            "/press-releases/500/",
            "ACRA ASSIGNS A(RU) TO FIRST ISSUER, OUTLOOK STABLE",
            "16 Jun 2026",
        ),
        (
            "/press-releases/500/",
            "ACRA ASSIGNS A+(RU) TO SECOND ISSUER, OUTLOOK STABLE",
            "16 Jun 2026",
        ),
    )
    with pytest.raises(
        AcraRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.DUPLICATE_CONFLICT.value,
    ):
        parse_acra_issuer_rating_actions_html(payload, retrieved_at=NOW)


def test_parser_rejects_empty_or_non_utf8_payload() -> None:
    for payload, code in (
        (b"", CreditRatingSourceErrorCode.EMPTY),
        (b"\xff\xfe\xfa", CreditRatingSourceErrorCode.HTML_INVALID),
    ):
        with pytest.raises(AcraRatingActionsSourceError, match=code.value):
            parse_acra_issuer_rating_actions_html(payload, retrieved_at=NOW)


def test_fetch_success_uses_only_fixed_endpoint() -> None:
    payload = _page(
        (
            "/press-releases/600/",
            "ACRA AFFIRMS AA(RU) TO TEST ISSUER, OUTLOOK POSITIVE",
            "16 Jun 2026",
        ),
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=payload,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_acra_issuer_rating_actions(
            client=client,
            retrieved_at=NOW,
        )

    assert result.status is CreditRatingSourceStatus.AVAILABLE
    assert result.records[0].outlook is CreditRatingOutlook.POSITIVE
    assert [str(request.url) for request in requests] == [
        ACRA_RATING_ACTIONS_ENDPOINT
    ]
    assert requests[0].headers.get("authorization") is None
    assert requests[0].headers.get("cookie") is None


@pytest.mark.parametrize(
    ("response", "expected_code"),
    [
        (
            httpx.Response(503, content=b"unavailable"),
            CreditRatingSourceErrorCode.HTTP_ERROR,
        ),
        (
            httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=b"{}",
            ),
            CreditRatingSourceErrorCode.CONTENT_TYPE_INVALID,
        ),
        (
            httpx.Response(
                200,
                headers={
                    "content-type": "text/html",
                    "content-length": "1000",
                },
                content=b"x",
            ),
            CreditRatingSourceErrorCode.RESPONSE_TOO_LARGE,
        ),
    ],
)
def test_fetch_returns_redacted_unavailable_results(
    response: httpx.Response,
    expected_code: CreditRatingSourceErrorCode,
) -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda _request: response)
    ) as client:
        result = fetch_acra_issuer_rating_actions(
            client=client,
            retrieved_at=NOW,
            max_response_bytes=100,
        )

    assert result.status is CreditRatingSourceStatus.UNAVAILABLE
    assert result.error_code is expected_code
    assert result.source is None
    assert result.records == ()


def test_fetch_maps_network_error_without_exception_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private upstream detail", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = fetch_acra_issuer_rating_actions(
            client=client,
            retrieved_at=NOW,
        )

    assert result.error_code is CreditRatingSourceErrorCode.NETWORK_ERROR
    assert "private upstream detail" not in result.model_dump_json()


def test_source_module_has_no_route_startup_or_write_surface() -> None:
    import omni_cio.market.acra_rating_actions_v1 as module

    assert not hasattr(module, "app")
    assert not hasattr(module, "router")
    assert not hasattr(module, "startup")
    assert not hasattr(module, "create_order")
    assert not hasattr(module, "post_order")
    assert not hasattr(module, "cancel_order")
