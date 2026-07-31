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
            f'<a href="{href}" class="date">{published_on}</a>'
            "</article>"
        )
        for href, title, published_on in items
    )
    return (
        "<html><body><h1>Рейтинговые действия</h1>"
        f"{cards}<h2>Аналитика</h2></body></html>"
    ).encode()


def test_contract_enforces_agency_scale_and_usage_flags() -> None:
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
    assert snapshot.informational_use_only is True
    assert snapshot.redistribution_authorized is False
    assert snapshot.investment_recommendation is False
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


def test_parser_extracts_five_actions_and_normalizes_glyphs() -> None:
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
                "ООО «Тест» на уровне ruВВ+ со стабильным прогнозом"
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
                "ruС и изменил прогноз по рейтингу на развивающийся"
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


def test_parser_supports_ru_rd_and_ru_d() -> None:
    result = parse_expert_ra_issuer_rating_actions_html(
        _page(
            (
                "/releases/2026/jul23a",
                "«Эксперт РА» подтвердил кредитный рейтинг АО «RD» на уровне ruРД",
                "23.07.2026",
            ),
            (
                "/releases/2026/jul22a",
                "«Эксперт РА» понизил кредитный рейтинг АО «D» до уровня ruД",
                "22.07.2026",
            ),
        ),
        retrieved_at=NOW,
    )
    assert [item.rating for item in result.records] == ["ruRD", "ruD"]


def test_parser_limits_scope_and_skips_unsupported_actions() -> None:
    payload = (
        "<html><body>"
        '<a href="/releases/2026/jul21z">'
        "«Эксперт РА» присвоил кредитный рейтинг ВНЕ БЛОКА на уровне ruAAA"
        "</a><span>21.07.2026</span>"
        "<h1>Рейтинговые действия</h1>"
        '<a href="/releases/2026/jul20a">'
        "«Эксперт РА» подтвердил кредитный рейтинг облигаций ООО «Тест» "
        "серии 001Р-01 на уровне ruA</a><span>20.07.2026</span>"
        '<a href="/releases/2026/jul20b">'
        "«Эксперт РА» пересмотрел и присвоил кредитный рейтинг АО «Сложный» "
        "на уровне ruAA</a><span>20.07.2026</span>"
        '<a href="/releases/2026/jul20c">'
        "«Эксперт РА» подтвердил кредитный рейтинг International на уровне BB"
        "</a><span>20.07.2026</span>"
        '<a href="/releases/2026/jul20d">'
        "«Эксперт РА» подтвердил кредитный рейтинг АО «Эмитент» на уровне ruAA"
        "</a><span>20.07.2026</span>"
        "<h2>Аналитика</h2></body></html>"
    ).encode()
    result = parse_expert_ra_issuer_rating_actions_html(payload, retrieved_at=NOW)
    assert [record.subject_name for record in result.records] == ["АО «Эмитент»"]


@pytest.mark.parametrize(
    "title",
    [
        "«Эксперт РА» подтвердил кредитный рейтинг АО «Тест» на уровне",
        (
            "«Эксперт РА» подтвердил кредитный рейтинг АО «Тест» "
            "на уровне ruA неизвестный хвост"
        ),
    ],
)
def test_parser_rejects_malformed_supported_titles(title: str) -> None:
    with pytest.raises(ExpertRaRatingActionsSourceError):
        parse_expert_ra_issuer_rating_actions_html(
            _page(("/releases/2026/jul19a", title, "19.07.2026")),
            retrieved_at=NOW,
        )


@pytest.mark.parametrize(
    "href",
    [
        "https://example.com/releases/2026/jul18a",
        "/releases/2026/not-a-release",
        "/releases/2026/jul18a?tracking=1",
        "/other/2026/jul18a",
    ],
)
def test_parser_rejects_release_urls_outside_fixed_scope(href: str) -> None:
    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.URL_INVALID.value,
    ):
        parse_expert_ra_issuer_rating_actions_html(
            _page(
                (
                    href,
                    (
                        "«Эксперт РА» присвоил кредитный рейтинг "
                        "АО «Тест» на уровне ruA"
                    ),
                    "18.07.2026",
                )
            ),
            retrieved_at=NOW,
        )


def test_parser_canonicalizes_fixed_www_alias() -> None:
    result = parse_expert_ra_issuer_rating_actions_html(
        _page(
            (
                "https://www.raexpert.ru/releases/2026/jul18a",
                "«Эксперт РА» присвоил кредитный рейтинг АО «Тест» на уровне ruA",
                "18.07.2026",
            )
        ),
        retrieved_at=NOW,
    )
    assert result.records[0].release_url == (
        "https://raexpert.ru/releases/2026/jul18a"
    )


def test_parser_rejects_missing_scope_date_and_future_date() -> None:
    missing_scope = (
        '<a href="/releases/2026/jul17a">'
        "«Эксперт РА» присвоил кредитный рейтинг АО «Тест» на уровне ruA"
        "</a><span>17.07.2026</span>"
    ).encode()
    missing_date = (
        "<h1>Рейтинговые действия</h1>"
        '<a href="/releases/2026/jul17a">'
        "«Эксперт РА» присвоил кредитный рейтинг АО «Тест» на уровне ruA"
        "</a><h2>Аналитика</h2>"
    ).encode()
    for payload, code in (
        (missing_scope, CreditRatingSourceErrorCode.SCHEMA_INVALID),
        (missing_date, CreditRatingSourceErrorCode.TIMESTAMP_INVALID),
    ):
        with pytest.raises(ExpertRaRatingActionsSourceError, match=code.value):
            parse_expert_ra_issuer_rating_actions_html(payload, retrieved_at=NOW)

    with pytest.raises(
        ExpertRaRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value,
    ):
        parse_expert_ra_issuer_rating_actions_html(
            _page(
                (
                    "/releases/2026/aug02a",
                    (
                        "«Эксперт РА» присвоил кредитный рейтинг "
                        "АО «Тест» на уровне ruA"
                    ),
                    "02.08.2026",
                )
            ),
            retrieved_at=NOW,
        )


def test_parser_rejects_duplicate_conflict_empty_and_non_utf8() -> None:
    conflicting = _page(
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
        parse_expert_ra_issuer_rating_actions_html(conflicting, retrieved_at=NOW)

    for payload, code in (
        (b"", CreditRatingSourceErrorCode.EMPTY),
        (b"\xff\xfe\xfa", CreditRatingSourceErrorCode.HTML_INVALID),
        (
            _page(
                (
                    "/releases/2026/jul15a",
                    "«Эксперт РА» опубликовал исследование",
                    "15.07.2026",
                )
            ),
            CreditRatingSourceErrorCode.EMPTY,
        ),
    ):
        with pytest.raises(ExpertRaRatingActionsSourceError, match=code.value):
            parse_expert_ra_issuer_rating_actions_html(payload, retrieved_at=NOW)


def test_script_content_is_ignored() -> None:
    payload = (
        "<html><body><h1>Рейтинговые действия</h1><script>"
        '<a href="/releases/2026/jul14a">'
        "«Эксперт РА» присвоил кредитный рейтинг АО «Подмена» на уровне ruAAA"
        "</a><span>14.07.2026</span></script>"
        '<a href="/releases/2026/jul14b">'
        "«Эксперт РА» подтвердил кредитный рейтинг АО «Настоящий» на уровне ruA"
        '</a><a href="/releases/2026/jul14b">14.07.2026</a>'
        "<h2>Аналитика</h2></body></html>"
    ).encode()
    result = parse_expert_ra_issuer_rating_actions_html(payload, retrieved_at=NOW)
    assert [record.subject_name for record in result.records] == ["АО «Настоящий»"]


def test_fetch_success_uses_fixed_endpoint_without_credentials() -> None:
    payload = _page(
        (
            "/releases/2026/jul13a",
            "«Эксперт РА» подтвердил кредитный рейтинг АО «Тест» на уровне ruAA",
            "13.07.2026",
        )
    )
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=payload,
        )

    result = fetch_expert_ra_issuer_rating_actions(
        transport=httpx.MockTransport(handler),
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
def test_fetch_returns_redacted_unavailable(
    response: httpx.Response,
    expected_code: CreditRatingSourceErrorCode,
) -> None:
    result = fetch_expert_ra_issuer_rating_actions(
        transport=httpx.MockTransport(lambda _request: response),
        retrieved_at=NOW,
        max_response_bytes=100,
    )
    assert result.status is CreditRatingSourceStatus.UNAVAILABLE
    assert result.error_code is expected_code
    assert result.source is None
    assert result.records == ()


def test_fetch_maps_network_and_parser_errors_without_text() -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private upstream detail", request=request)

    network = fetch_expert_ra_issuer_rating_actions(
        transport=httpx.MockTransport(broken),
        retrieved_at=NOW,
    )
    assert network.error_code is CreditRatingSourceErrorCode.NETWORK_ERROR
    assert "private upstream detail" not in network.model_dump_json()

    malformed = _page(
        (
            "/releases/2026/jul12a",
            "«Эксперт РА» подтвердил кредитный рейтинг АО «Тест» на уровне",
            "12.07.2026",
        )
    )
    parser_failure = fetch_expert_ra_issuer_rating_actions(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=malformed,
            )
        ),
        retrieved_at=NOW,
    )
    assert parser_failure.error_code is CreditRatingSourceErrorCode.SCHEMA_INVALID


def test_invalid_controls_make_no_request() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"")

    for kwargs in (
        {"timeout_seconds": 0},
        {"timeout_seconds": True},
        {"max_response_bytes": 0},
        {"max_response_bytes": True},
    ):
        result = fetch_expert_ra_issuer_rating_actions(
            transport=httpx.MockTransport(handler),
            retrieved_at=NOW,
            **kwargs,
        )
        assert result.error_code is CreditRatingSourceErrorCode.SCHEMA_INVALID
    assert calls == 0


def test_module_has_no_generic_url_startup_route_or_write_surface() -> None:
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
