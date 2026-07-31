from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.expert_ra_ratings import (
    ExpertRaIssuerRatingActionsSnapshotV1,
    ExpertRaIssuerRatingActionV1,
)
from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.ratings import (
    CreditRatingOutlook,
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)
from omni_cio.market.expert_ra_rating_actions_v1 import (
    EXPERT_RA_RATING_ACTIONS_ENDPOINT,
    EXPERT_RA_RATING_ACTIONS_SOURCE_ID,
    ExpertRaRatingActionsSourceError,
    fetch_expert_ra_issuer_rating_actions,
    parse_expert_ra_issuer_rating_actions_html,
)


NOW = datetime(2026, 7, 31, 5, 30, tzinfo=timezone.utc)


def _source() -> MarketSourceV1:
    return MarketSourceV1(
        provider="Expert RA",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id=EXPERT_RA_RATING_ACTIONS_SOURCE_ID,
    )


def _page(*items: tuple[str, str, str]) -> bytes:
    cards = "".join(
        (
            '<article class="rating-action">'
            f'<a href="{href}"><span>{title}</span></a>'
            f"<time>{published_on}</time>"
            "</article>"
        )
        for href, title, published_on in items
    )
    return f"<html><body>{cards}</body></html>".encode()


def test_contract_enforces_agency_identity_scale_and_withdrawn_semantics() -> None:
    record = ExpertRaIssuerRatingActionV1(
        subject_name='АО "ФИНАМ"',
        rating="ruA",
        action=RatingAction.ASSIGNED,
        outlook=CreditRatingOutlook.STABLE,
        published_on=NOW.date(),
        release_url="https://raexpert.ru/releases/2026/jul28b",
        source=_source(),
    )
    snapshot = ExpertRaIssuerRatingActionsSnapshotV1(
        retrieved_at=NOW,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=_source(),
        records=(record,),
    )
    assert snapshot.records == (record,)
    assert snapshot.agency_specific_scale_only is True
    assert snapshot.trading_methods is False

    with pytest.raises(ValidationError):
        ExpertRaIssuerRatingActionV1(
            subject_name="Issuer",
            rating="A(RU)",
            action=RatingAction.AFFIRMED,
            published_on=NOW.date(),
            release_url="https://raexpert.ru/releases/2026/jul28c",
            source=_source(),
        )
    with pytest.raises(ValidationError):
        ExpertRaIssuerRatingActionV1(
            subject_name="Issuer",
            rating="ruA",
            action=RatingAction.WITHDRAWN,
            published_on=NOW.date(),
            release_url="https://raexpert.ru/releases/2026/jul28d",
            source=_source(),
        )


def test_parser_extracts_five_issuer_actions_and_sorts_newest_first() -> None:
    payload = _page(
        (
            "/releases/2026/jul28b",
            "«Эксперт РА» присвоил кредитный рейтинг АО «ФИНАМ» на уровне ruA",
            "28.07.2026",
        ),
        (
            "/releases/2026/jul27a",
            (
                "«Эксперт РА» подтвердил рейтинг кредитоспособности "
                "ООО «Тест» на уровне ruВВ+, прогноз стабильный"
            ),
            "27.07.2026",
        ),
        (
            "/releases/2026/jul26c",
            "«Эксперт РА» повысил кредитный рейтинг АО «Рост» до уровня ruАА-",
            "26.07.2026",
        ),
        (
            "/releases/2026/jul25d",
            (
                "«Эксперт РА» понизил кредитный рейтинг АО «Риск» до уровня "
                "ruС, изменил прогноз на развивающийся и продлил статус "
                "«под наблюдением»"
            ),
            "25.07.2026",
        ),
        (
            "/releases/2026/jul24e",
            "«Эксперт РА» отозвал без подтверждения кредитный рейтинг ООО «Выход»",
            "24.07.2026",
        ),
    )

    result = parse_expert_ra_issuer_rating_actions_html(payload, retrieved_at=NOW)

    assert result.status is CreditRatingSourceStatus.AVAILABLE
    assert [record.action for record in result.records] == [
        RatingAction.ASSIGNED,
        RatingAction.AFFIRMED,
        RatingAction.UPGRADED,
        RatingAction.DOWNGRADED,
        RatingAction.WITHDRAWN,
    ]
    assert [record.rating for record in result.records] == [
        "ruA",
        "ruBB+",
        "ruAA-",
        "ruC",
        None,
    ]
    assert result.records[1].outlook is CreditRatingOutlook.STABLE
    assert result.records[3].outlook is CreditRatingOutlook.DEVELOPING
    assert result.records[4].outlook is None


def test_parser_skips_issue_structured_esg_and_plural_actions() -> None:
    payload = _page(
        (
            "/releases/2026/jul20a",
            (
                "«Эксперт РА» подтвердил кредитный рейтинг облигаций "
                "ООО «Тест» серии 001Р-01 на уровне ruA"
            ),
            "20.07.2026",
        ),
        (
            "/releases/2026/jul20b",
            (
                "«Эксперт РА» присвоил кредитный рейтинг инструмента "
                "структурированного финансирования на уровне ruAAA"
            ),
            "20.07.2026",
        ),
        (
            "/releases/2026/jul20c",
            "«Эксперт РА» присвоил рейтинг ESG АО «Зеленая компания» на уровне ESG-A",
            "20.07.2026",
        ),
        (
            "/releases/2026/jul20d",
            "«Эксперт РА» подтвердил кредитные рейтинги двум компаниям",
            "20.07.2026",
        ),
        (
            "/releases/2026/jul20e",
            "«Эксперт РА» подтвердил кредитный рейтинг АО «Эмитент» на уровне ruAA",
            "20.07.2026",
        ),
    )

    result = parse_expert_ra_issuer_rating_actions_html(payload, retrieved_at=NOW)

    assert len(result.records) == 1
    assert result.records[0].subject_name == "АО «Эмитент»"


def test_parser_rejects_malformed_supported_issuer_action() -> None:
    payload = _page(
        (
            "/releases/2026/jul19a",
            "«Эксперт РА» подтвердил кредитный рейтинг АО «Тест» на уровне",
            "19.07.2026",
        ),
    )
    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.SCHEMA_INVALID.value,
    ):
        parse_expert_ra_issuer_rating_actions_html(payload, retrieved_at=NOW)


@pytest.mark.parametrize(
    ("href", "expected_code"),
    [
        (
            "https://example.com/releases/2026/jul18a",
            CreditRatingSourceErrorCode.URL_INVALID,
        ),
        (
            "https://www.raexpert.ru/releases/2026/jul18a",
            CreditRatingSourceErrorCode.URL_INVALID,
        ),
        (
            "/releases/2026/not-a-release",
            CreditRatingSourceErrorCode.URL_INVALID,
        ),
        (
            "/releases/2026/jul18a?tracking=1",
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
            "«Эксперт РА» присвоил кредитный рейтинг АО «Тест» на уровне ruA",
            "18.07.2026",
        ),
    )
    with pytest.raises(ExpertRaRatingActionsSourceError, match=expected_code.value):
        parse_expert_ra_issuer_rating_actions_html(payload, retrieved_at=NOW)


def test_parser_rejects_missing_or_future_publication_date() -> None:
    missing = (
        '<a href="/releases/2026/jul17a">'
        "«Эксперт РА» присвоил кредитный рейтинг АО «Тест» на уровне ruA"
        "</a>"
    ).encode()
    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value,
    ):
        parse_expert_ra_issuer_rating_actions_html(missing, retrieved_at=NOW)

    future = _page(
        (
            "/releases/2026/aug02a",
            "«Эксперт РА» присвоил кредитный рейтинг АО «Тест» на уровне ruA",
            "02.08.2026",
        ),
    )
    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value,
    ):
        parse_expert_ra_issuer_rating_actions_html(future, retrieved_at=NOW)


def test_parser_rejects_conflicting_duplicate_release() -> None:
    payload = _page(
        (
            "/releases/2026/jul16a",
            "«Эксперт РА» присвоил кредитный рейтинг АО «Первый» на уровне ruA",
            "16.07.2026",
        ),
        (
            "/releases/2026/jul16a",
            "«Эксперт РА» присвоил кредитный рейтинг АО «Второй» на уровне ruA+",
            "16.07.2026",
        ),
    )
    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.DUPLICATE_CONFLICT.value,
    ):
        parse_expert_ra_issuer_rating_actions_html(payload, retrieved_at=NOW)


def test_parser_rejects_empty_non_utf8_and_no_supported_records() -> None:
    for payload, code in (
        (b"", CreditRatingSourceErrorCode.EMPTY),
        (b"\xff\xfe\xfa", CreditRatingSourceErrorCode.HTML_INVALID),
        (
            _page(
                (
                    "/releases/2026/jul15a",
                    "«Эксперт РА» опубликовал исследование",
                    "15.07.2026",
                ),
            ),
            CreditRatingSourceErrorCode.EMPTY,
        ),
    ):
        with pytest.raises(ExpertRaRatingActionsSourceError, match=code.value):
            parse_expert_ra_issuer_rating_actions_html(payload, retrieved_at=NOW)


def test_script_content_is_not_parsed_as_rating_action() -> None:
    payload = (
        "<html><body><script>"
        '<a href="/releases/2026/jul14a">'
        "«Эксперт РА» присвоил кредитный рейтинг АО «Подмена» на уровне ruAAA"
        "</a><time>14.07.2026</time></script>"
        '<a href="/releases/2026/jul14b">'
        "«Эксперт РА» подтвердил кредитный рейтинг АО «Настоящий» на уровне ruA"
        "</a><time>14.07.2026</time></body></html>"
    ).encode()
    result = parse_expert_ra_issuer_rating_actions_html(payload, retrieved_at=NOW)
    assert [record.subject_name for record in result.records] == ["АО «Настоящий»"]


def test_fetch_success_uses_only_fixed_endpoint_without_credentials() -> None:
    payload = _page(
        (
            "/releases/2026/jul13a",
            "«Эксперт РА» подтвердил кредитный рейтинг АО «Тест» на уровне ruAA",
            "13.07.2026",
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
        result = fetch_expert_ra_issuer_rating_actions(
            client=client,
            retrieved_at=NOW,
        )

    assert result.status is CreditRatingSourceStatus.AVAILABLE
    assert [str(request.url) for request in requests] == [
        EXPERT_RA_RATING_ACTIONS_ENDPOINT
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
                headers={"content-type": "text/html", "content-length": "1000"},
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
        result = fetch_expert_ra_issuer_rating_actions(
            client=client,
            retrieved_at=NOW,
            max_response_bytes=100,
        )

    assert result.status is CreditRatingSourceStatus.UNAVAILABLE
    assert result.error_code is expected_code
    assert result.source is None
    assert result.records == ()


def test_fetch_maps_network_and_parser_errors_without_upstream_text() -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private upstream detail", request=request)

    with httpx.Client(transport=httpx.MockTransport(broken)) as client:
        network = fetch_expert_ra_issuer_rating_actions(
            client=client,
            retrieved_at=NOW,
        )
    assert network.status is CreditRatingSourceStatus.UNAVAILABLE
    assert network.error_code is CreditRatingSourceErrorCode.NETWORK_ERROR
    assert "private upstream detail" not in network.model_dump_json()

    malformed = _page(
        (
            "/releases/2026/jul12a",
            "«Эксперт РА» подтвердил кредитный рейтинг АО «Тест» на уровне",
            "12.07.2026",
        ),
    )
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=malformed,
            )
        )
    ) as client:
        parser_failure = fetch_expert_ra_issuer_rating_actions(
            client=client,
            retrieved_at=NOW,
        )
    assert parser_failure.status is CreditRatingSourceStatus.UNAVAILABLE
    assert parser_failure.error_code is CreditRatingSourceErrorCode.SCHEMA_INVALID


def test_invalid_fetch_controls_fail_closed_without_request() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        for kwargs in (
            {"timeout_seconds": 0},
            {"timeout_seconds": True},
            {"max_response_bytes": 0},
            {"max_response_bytes": True},
        ):
            result = fetch_expert_ra_issuer_rating_actions(
                client=client,
                retrieved_at=NOW,
                **kwargs,
            )
            assert result.status is CreditRatingSourceStatus.UNAVAILABLE
            assert result.error_code is CreditRatingSourceErrorCode.SCHEMA_INVALID
    assert calls == 0


def test_module_has_no_generic_url_startup_route_or_broker_write_surface() -> None:
    import omni_cio.market.expert_ra_rating_actions_v1 as module

    assert module.EXPERT_RA_RATING_ACTIONS_ENDPOINT == "https://raexpert.ru/"
    for forbidden in (
        "app",
        "router",
        "startup",
        "generic_url",
        "agency_url",
        "create_order",
        "post_order",
        "cancel_order",
    ):
        assert not hasattr(module, forbidden)
