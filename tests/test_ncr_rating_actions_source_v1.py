from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast

import httpx
import pytest
from pydantic import ValidationError

from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.ncr_ratings import (
    NcrIssuerRatingActionsSnapshotV1,
    NcrIssuerRatingActionV1,
)
from omni_cio.contracts.v1.ratings import (
    CreditRatingOutlook,
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)
from omni_cio.market.ncr_rating_actions_v1 import (
    NCR_RATING_ACTIONS_ENDPOINT,
    NCR_RATING_ACTIONS_SOURCE_ID,
    NcrRatingActionsSourceError,
    fetch_ncr_issuer_rating_actions,
    parse_ncr_issuer_rating_actions_html,
)


NOW = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)


def _source() -> MarketSourceV1:
    return MarketSourceV1(
        provider="NCR",
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=NOW,
        source_id=NCR_RATING_ACTIONS_SOURCE_ID,
    )


def _page(*items: tuple[str, str, str, str]) -> bytes:
    rows = "".join(
        (
            "<tr>"
            f'<td><a href="{href}"><span>{title}</span></a></td>'
            f"<td>{sector}</td><td><time>{published_on}</time></td>"
            "</tr>"
        )
        for href, title, sector, published_on in items
    )
    return (
        "<html><body><h1>Пресс-релизы</h1><table>"
        "<thead><tr><th>Название</th><th>Сектор</th>"
        "<th>Дата</th><th>Скачать</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></body></html>"
    ).encode()


def _item(
    suffix: str,
    title: str,
    published_on: str,
    sector: str = "Нефинансовые",
) -> tuple[str, str, str, str]:
    return (
        f"/ratings/press-releases/{suffix}/",
        title,
        sector,
        published_on,
    )


def test_contract_enforces_ncr_identity_scale_and_usage_flags() -> None:
    record = NcrIssuerRatingActionV1(
        subject_name="АО «Русский краб»",
        rating="A.ru",
        action=RatingAction.ASSIGNED,
        outlook=CreditRatingOutlook.STABLE,
        published_on=NOW.date(),
        release_url=("https://ratings.ru/ratings/press-releases/RusCrab-RA-010826/"),
        source=_source(),
    )
    snapshot = NcrIssuerRatingActionsSnapshotV1(
        retrieved_at=NOW,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=_source(),
        records=(record,),
    )

    assert snapshot.records == (record,)
    assert snapshot.fixed_official_source is True
    assert snapshot.issuer_scope_only is True
    assert snapshot.agency_specific_scale_only is True
    assert snapshot.cross_agency_identity_merged is False
    assert snapshot.informational_use_only is True
    assert snapshot.redistribution_authorized is False
    assert snapshot.investment_recommendation is False
    assert snapshot.trading_methods is False

    for invalid_rating in ("ruA", "A(RU)", "eA.ru", "RD", "D.ru"):
        with pytest.raises(ValidationError):
            NcrIssuerRatingActionV1(
                subject_name="Issuer",
                rating=invalid_rating,
                action=RatingAction.AFFIRMED,
                published_on=NOW.date(),
                release_url=(
                    "https://ratings.ru/ratings/press-releases/Issuer-RA-010826/"
                ),
                source=_source(),
            )


def test_contract_rejects_wrong_source_url_date_and_withdrawal_payload() -> None:
    common = {
        "subject_name": "ООО «Тест»",
        "rating": "A.ru",
        "action": RatingAction.AFFIRMED,
        "published_on": NOW.date(),
        "release_url": ("https://ratings.ru/ratings/press-releases/Test-RA-010826/"),
        "source": _source(),
    }
    for update in (
        {
            "source": MarketSourceV1(
                provider="NCR",
                authority=SourceAuthority.SECONDARY,
                retrieved_at=NOW,
                source_id=NCR_RATING_ACTIONS_SOURCE_ID,
            )
        },
        {"release_url": "https://example.com/Test-RA-010826/"},
        {"release_url": ("https://ratings.ru/ratings/press-releases/Test-RA-310726/")},
        {"release_url": ("https://ratings.ru/ratings/press-releases/Test-ra-010826/")},
        {"action": RatingAction.WITHDRAWN},
    ):
        with pytest.raises(ValidationError):
            NcrIssuerRatingActionV1(**(common | update))


@pytest.mark.parametrize(
    "rating",
    [
        "AAA.ru",
        "AA+.ru",
        "AA.ru",
        "AA-.ru",
        "A+.ru",
        "A.ru",
        "A-.ru",
        "BBB+.ru",
        "BBB.ru",
        "BBB-.ru",
        "BB+.ru",
        "BB.ru",
        "BB-.ru",
        "B+.ru",
        "B.ru",
        "B-.ru",
        "CCC.ru",
        "CC.ru",
        "C.ru",
        "D",
    ],
)
def test_contract_accepts_exact_ncr_national_scale(rating: str) -> None:
    record = NcrIssuerRatingActionV1(
        subject_name="Issuer",
        rating=rating,
        action=RatingAction.AFFIRMED,
        published_on=NOW.date(),
        release_url=("https://ratings.ru/ratings/press-releases/Issuer-RA-010826/"),
        source=_source(),
    )
    assert record.rating == rating


def test_snapshot_rejects_timestamp_order_duplicate_and_size_mismatch() -> None:
    records = tuple(
        NcrIssuerRatingActionV1(
            subject_name=f"Issuer {index}",
            rating="A.ru",
            action=RatingAction.AFFIRMED,
            published_on=(NOW - timedelta(days=index)).date(),
            release_url=(
                "https://ratings.ru/ratings/press-releases/"
                f"Issuer{index}-RA-{(NOW - timedelta(days=index)):%d%m%y}/"
            ),
            source=_source(),
        )
        for index in range(31)
    )

    for update in (
        {"retrieved_at": NOW - timedelta(seconds=1)},
        {"records": (records[1], records[0])},
        {"records": (records[0], records[0])},
        {"records": records},
    ):
        payload = {
            "retrieved_at": NOW,
            "status": CreditRatingSourceStatus.AVAILABLE,
            "source": _source(),
            "records": (records[0],),
        }
        with pytest.raises(ValidationError):
            NcrIssuerRatingActionsSnapshotV1(**(payload | update))


def test_parser_and_snapshot_reject_naive_retrieval_time() -> None:
    naive = datetime(2026, 8, 1, 9, 0)
    with pytest.raises(
        NcrRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value,
    ):
        parse_ncr_issuer_rating_actions_html(
            _page(
                _item(
                    "Test-RA-010826",
                    "НКР присвоило ООО «Тест» кредитный рейтинг A.ru",
                    "01.08.2026",
                )
            ),
            retrieved_at=naive,
        )

    with pytest.raises(ValidationError):
        NcrIssuerRatingActionsSnapshotV1(
            retrieved_at=naive,
            status=CreditRatingSourceStatus.UNAVAILABLE,
            error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
        )


def test_parser_extracts_five_actions_and_normalizes_glyphs() -> None:
    result = parse_ncr_issuer_rating_actions_html(
        _page(
            _item(
                "RusCrab-RA-010826",
                (
                    "НКР присвоило АО «Русский краб» кредитный рейтинг "
                    "A.ru со стабильным прогнозом"
                ),
                "01.08.2026",
            ),
            _item(
                "OSK-RA-310726",
                (
                    "НКР подтвердило кредитный рейтинг АО «ОСК» "
                    "на уровне AАА.ru, прогноз — стабильный"
                ),
                "31.07.2026",
            ),
            _item(
                "Invitro-RA-240726",
                (
                    "НКР повысило кредитный рейтинг АО «Инвитро» "
                    "с A.ru до A+.ru, прогноз изменён на стабильный"
                ),
                "24.07.2026",
            ),
            _item(
                "Kronos-RA-280726",
                (
                    "НКР снизило кредитный рейтинг ООО «КРОНОС» "
                    "с BB+.ru до B.ru, прогноз — негативный"
                ),
                "28.07.2026",
            ),
            _item(
                "GTS-RA-170426",
                ("НКР отозвало кредитный рейтинг ООО «ГТС» без подтверждения"),
                "17.04.2026",
            ),
        ),
        retrieved_at=NOW,
    )

    assert [record.action for record in result.records] == [
        RatingAction.ASSIGNED,
        RatingAction.AFFIRMED,
        RatingAction.DOWNGRADED,
        RatingAction.UPGRADED,
        RatingAction.WITHDRAWN,
    ]
    assert [record.rating for record in result.records] == [
        "A.ru",
        "AAA.ru",
        "B.ru",
        "A+.ru",
        None,
    ]
    assert result.records[2].outlook is CreditRatingOutlook.NEGATIVE
    assert result.records[4].outlook is None
    assert result.records[4].subject_name == "ООО «ГТС»"


@pytest.mark.parametrize(
    ("tail", "expected"),
    [
        ("со стабильным прогнозом", CreditRatingOutlook.STABLE),
        ("с позитивным прогнозом", CreditRatingOutlook.POSITIVE),
        (", прогноз — негативный", CreditRatingOutlook.NEGATIVE),
        (", прогноз изменён на развивающийся", CreditRatingOutlook.DEVELOPING),
        (
            ", прогноз — «рейтинг на пересмотре с возможностью понижения»",
            CreditRatingOutlook.UNDER_REVISION,
        ),
        (
            ", прогноз — «рейтинг на пересмотре — неопределённый прогноз»",
            CreditRatingOutlook.UNDER_REVISION,
        ),
        (
            ", прогноз изменен на неопределенный",
            CreditRatingOutlook.UNDER_REVISION,
        ),
    ],
)
def test_parser_supports_fixed_ncr_outlook_grammar(
    tail: str,
    expected: CreditRatingOutlook,
) -> None:
    result = parse_ncr_issuer_rating_actions_html(
        _page(
            _item(
                "Outlook-RA-010826",
                (
                    "НКР подтвердило кредитный рейтинг ООО «Тест» "
                    f"на уровне BB.ru {tail}"
                ),
                "01.08.2026",
            )
        ),
        retrieved_at=NOW,
    )
    assert result.records[0].outlook is expected


@pytest.mark.parametrize(
    "tail",
    [
        ", прогноз — «рейтинг на пересмотре выполнить инструкцию»",
        ", прогноз — «рейтинг на пересмотре с возможностью понижения",
        ", прогноз — рейтинг на пересмотре с возможностью удаления",
    ],
)
def test_parser_rejects_unbounded_or_unbalanced_under_revision_tail(
    tail: str,
) -> None:
    with pytest.raises(
        NcrRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.OUTLOOK_INVALID.value,
    ):
        parse_ncr_issuer_rating_actions_html(
            _page(
                _item(
                    "Outlook-RA-010826",
                    (
                        "НКР подтвердило кредитный рейтинг ООО «Тест» "
                        f"на уровне BB.ru {tail}"
                    ),
                    "01.08.2026",
                )
            ),
            retrieved_at=NOW,
        )


def test_parser_supports_d_without_ru_suffix() -> None:
    result = parse_ncr_issuer_rating_actions_html(
        _page(
            _item(
                "Default-RA-310726",
                ("НКР понизило кредитный рейтинг ООО «Риск» с C.ru до D"),
                "31.07.2026",
            )
        ),
        retrieved_at=NOW,
    )
    assert result.records[0].rating == "D"
    assert result.records[0].action is RatingAction.DOWNGRADED


def test_parser_limits_scope_and_skips_unsupported_titles() -> None:
    result = parse_ncr_issuer_rating_actions_html(
        _page(
            _item(
                "Bond-RA-010826",
                (
                    "НКР присвоило выпуску биржевых облигаций ООО «Тест» "
                    "серии 001P-01 кредитный рейтинг A.ru"
                ),
                "01.08.2026",
            ),
            _item(
                "Mixed-RA-010826",
                (
                    "НКР подтвердило кредитные рейтинги АО «Тест» "
                    "и его облигаций на уровне AA.ru"
                ),
                "01.08.2026",
            ),
            _item(
                "Expected-RA-010826",
                ("НКР присвоило выпуску облигаций ожидаемый кредитный рейтинг eA.ru"),
                "01.08.2026",
            ),
            _item(
                "Forecast-RA-010826",
                (
                    "НКР изменило прогноз по кредитному рейтингу "
                    "ООО «Тест» на стабильный"
                ),
                "01.08.2026",
            ),
            _item(
                "Issuer-RA-310726",
                (
                    "НКР подтвердило кредитный рейтинг ООО «Настоящий» "
                    "на уровне AA.ru, прогноз — стабильный"
                ),
                "31.07.2026",
            ),
        ),
        retrieved_at=NOW,
    )
    assert [record.subject_name for record in result.records] == ["ООО «Настоящий»"]


@pytest.mark.parametrize(
    "title",
    [
        "НКР подтвердило кредитный рейтинг ООО «Тест» на уровне",
        (
            "НКР подтвердило кредитный рейтинг ООО «Тест» "
            "на уровне A.ru неизвестный хвост"
        ),
        ("НКР повысило кредитный рейтинг ООО «Тест» с A.ru до неизвестно"),
    ],
)
def test_parser_rejects_malformed_supported_titles(title: str) -> None:
    with pytest.raises(NcrRatingActionsSourceError):
        parse_ncr_issuer_rating_actions_html(
            _page(_item("Test-RA-010826", title, "01.08.2026")),
            retrieved_at=NOW,
        )


@pytest.mark.parametrize(
    "href",
    [
        "https://example.com/ratings/press-releases/Test-RA-010826/",
        "/ratings/press-releases/not-a-release/",
        "/ratings/press-releases/Test-RA-010826/?tracking=1",
        "/ratings/press-releases/Test-RA-010826/#fragment",
        "/other/Test-RA-010826/",
        "/ratings/press-releases/Test_RA_010826/",
    ],
)
def test_parser_rejects_release_urls_outside_fixed_scope(href: str) -> None:
    with pytest.raises(
        NcrRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.URL_INVALID.value,
    ):
        parse_ncr_issuer_rating_actions_html(
            _page(
                (
                    href,
                    (
                        "НКР присвоило ООО «Тест» кредитный рейтинг "
                        "A.ru со стабильным прогнозом"
                    ),
                    "Нефинансовые",
                    "01.08.2026",
                )
            ),
            retrieved_at=NOW,
        )


def test_parser_canonicalizes_www_alias_and_ra_case() -> None:
    result = parse_ncr_issuer_rating_actions_html(
        _page(
            (
                ("https://www.ratings.ru/ratings/press-releases/Test-ra-010826/"),
                "НКР присвоило ООО «Тест» кредитный рейтинг A.ru",
                "Нефинансовые",
                "01.08.2026",
            )
        ),
        retrieved_at=NOW,
    )
    assert result.records[0].release_url == (
        "https://ratings.ru/ratings/press-releases/Test-RA-010826/"
    )


def test_parser_binds_release_url_and_visible_publication_date() -> None:
    mismatch = _page(
        _item(
            "Test-RA-310726",
            "НКР присвоило ООО «Тест» кредитный рейтинг A.ru",
            "01.08.2026",
        )
    )
    invalid_calendar = _page(
        _item(
            "Test-RA-310226",
            "НКР присвоило ООО «Тест» кредитный рейтинг A.ru",
            "31.02.2026",
        )
    )
    future = _page(
        _item(
            "Test-RA-030826",
            "НКР присвоило ООО «Тест» кредитный рейтинг A.ru",
            "03.08.2026",
        )
    )
    for payload, code in (
        (mismatch, CreditRatingSourceErrorCode.IDENTITY_INVALID),
        (invalid_calendar, CreditRatingSourceErrorCode.URL_INVALID),
        (future, CreditRatingSourceErrorCode.TIMESTAMP_INVALID),
    ):
        with pytest.raises(NcrRatingActionsSourceError, match=code.value):
            parse_ncr_issuer_rating_actions_html(payload, retrieved_at=NOW)


def test_parser_requires_exact_list_headers_and_adjacent_date() -> None:
    missing_header = (
        '<a href="/ratings/press-releases/Test-RA-010826/">'
        "НКР присвоило ООО «Тест» кредитный рейтинг A.ru"
        "</a><span>01.08.2026</span>"
    ).encode()
    missing_date = (
        "<table><th>Название</th><th>Сектор</th><th>Дата</th>"
        '<a href="/ratings/press-releases/Test-RA-010826/">'
        "НКР присвоило ООО «Тест» кредитный рейтинг A.ru"
        "</a><span>Нефинансовые</span></table>"
    ).encode()
    for payload, code in (
        (missing_header, CreditRatingSourceErrorCode.SCHEMA_INVALID),
        (missing_date, CreditRatingSourceErrorCode.TIMESTAMP_INVALID),
    ):
        with pytest.raises(NcrRatingActionsSourceError, match=code.value):
            parse_ncr_issuer_rating_actions_html(payload, retrieved_at=NOW)


def test_parser_rejects_date_linked_to_different_release() -> None:
    payload = (
        "<table><th>Название</th><th>Сектор</th><th>Дата</th>"
        '<a href="/ratings/press-releases/First-RA-010826/">'
        "НКР присвоило ООО «Тест» кредитный рейтинг A.ru"
        "</a><span>Нефинансовые</span>"
        '<a href="/ratings/press-releases/Second-RA-010826/">'
        "01.08.2026</a></table>"
    ).encode()
    with pytest.raises(
        NcrRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.IDENTITY_INVALID.value,
    ):
        parse_ncr_issuer_rating_actions_html(payload, retrieved_at=NOW)


def test_parser_rejects_duplicate_href_and_link_header_impersonation() -> None:
    duplicate_href = (
        "<table><th>Название</th><th>Сектор</th><th>Дата</th>"
        '<a href="/ratings/press-releases/Test-RA-010826/" '
        'href="https://example.com/private">'
        "НКР присвоило ООО «Тест» кредитный рейтинг A.ru"
        "</a><span>Нефинансовые</span><span>01.08.2026</span></table>"
    ).encode()
    linked_headers = (
        "<table><a>Название</a><a>Сектор</a><a>Дата</a>"
        '<a href="/ratings/press-releases/Test-RA-010826/">'
        "НКР присвоило ООО «Тест» кредитный рейтинг A.ru"
        "</a><span>Нефинансовые</span><span>01.08.2026</span></table>"
    ).encode()

    for payload, code in (
        (duplicate_href, CreditRatingSourceErrorCode.HTML_INVALID),
        (linked_headers, CreditRatingSourceErrorCode.SCHEMA_INVALID),
    ):
        with pytest.raises(NcrRatingActionsSourceError, match=code.value):
            parse_ncr_issuer_rating_actions_html(payload, retrieved_at=NOW)


def test_parser_rejects_duplicate_conflict_and_deduplicates_exact_copy() -> None:
    exact = _item(
        "Same-RA-010826",
        "НКР присвоило ООО «Один» кредитный рейтинг A.ru",
        "01.08.2026",
    )
    result = parse_ncr_issuer_rating_actions_html(
        _page(exact, exact),
        retrieved_at=NOW,
    )
    assert len(result.records) == 1

    conflicting = _page(
        exact,
        _item(
            "Same-RA-010826",
            "НКР присвоило ООО «Другой» кредитный рейтинг A+.ru",
            "01.08.2026",
        ),
    )
    with pytest.raises(
        NcrRatingActionsSourceError,
        match=CreditRatingSourceErrorCode.DUPLICATE_CONFLICT.value,
    ):
        parse_ncr_issuer_rating_actions_html(conflicting, retrieved_at=NOW)


def test_parser_bounds_snapshot_to_newest_thirty_supported_records() -> None:
    items = tuple(
        _item(
            f"Issuer{index:02d}-RA-{index:02d}0726",
            (f"НКР присвоило ООО «Эмитент {index:02d}» кредитный рейтинг A.ru"),
            f"{index:02d}.07.2026",
        )
        for index in range(1, 32)
    )
    result = parse_ncr_issuer_rating_actions_html(
        _page(*reversed(items)),
        retrieved_at=NOW,
    )
    assert len(result.records) == 30
    assert result.records[0].published_on.isoformat() == "2026-07-31"
    assert result.records[-1].published_on.isoformat() == "2026-07-02"


def test_parser_rejects_empty_non_utf8_and_unclosed_sensitive_tags() -> None:
    for payload, code in (
        (b"", CreditRatingSourceErrorCode.EMPTY),
        (b"\xff\xfe\xfa", CreditRatingSourceErrorCode.HTML_INVALID),
        (
            (
                "<table><th>Название</th><th>Сектор</th><th>Дата</th><script>unclosed"
            ).encode(),
            CreditRatingSourceErrorCode.HTML_INVALID,
        ),
        (
            (
                "<table><th>Название</th><th>Сектор</th><th>Дата</th>"
                '<a href="/ratings/press-releases/Test-RA-010826/">'
                "unclosed"
            ).encode(),
            CreditRatingSourceErrorCode.HTML_INVALID,
        ),
    ):
        with pytest.raises(NcrRatingActionsSourceError, match=code.value):
            parse_ncr_issuer_rating_actions_html(payload, retrieved_at=NOW)


def test_script_content_is_ignored() -> None:
    payload = (
        "<table><th>Название</th><th>Сектор</th><th>Дата</th>"
        "<script>"
        '<a href="/ratings/press-releases/Fake-RA-010826/">'
        "НКР присвоило ООО «Подмена» кредитный рейтинг AAA.ru"
        "</a><span>Нефинансовые</span><span>01.08.2026</span>"
        "</script>"
        '<a href="/ratings/press-releases/Real-RA-310726/">'
        "НКР подтвердило кредитный рейтинг ООО «Настоящий» "
        "на уровне A.ru</a><span>Нефинансовые</span>"
        "<span>31.07.2026</span></table>"
    ).encode()
    result = parse_ncr_issuer_rating_actions_html(payload, retrieved_at=NOW)
    assert [record.subject_name for record in result.records] == ["ООО «Настоящий»"]


def test_fetch_success_uses_fixed_endpoint_without_credentials() -> None:
    payload = _page(
        _item(
            "Test-RA-010826",
            "НКР присвоило ООО «Тест» кредитный рейтинг A.ru",
            "01.08.2026",
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

    result = fetch_ncr_issuer_rating_actions(
        transport=httpx.MockTransport(handler),
        retrieved_at=NOW,
    )
    assert result.status is CreditRatingSourceStatus.AVAILABLE
    assert [str(request.url) for request in requests] == [NCR_RATING_ACTIONS_ENDPOINT]
    assert requests[0].headers.get("authorization") is None
    assert requests[0].headers.get("cookie") is None
    assert requests[0].method == "GET"


@pytest.mark.parametrize(
    ("response", "expected_code"),
    [
        (
            httpx.Response(503, content=b"private upstream body"),
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
        (
            httpx.Response(
                200,
                headers={"content-type": "text/html", "content-length": "bad"},
                content=b"x",
            ),
            CreditRatingSourceErrorCode.SCHEMA_INVALID,
        ),
    ],
)
def test_fetch_returns_redacted_unavailable(
    response: httpx.Response,
    expected_code: CreditRatingSourceErrorCode,
) -> None:
    result = fetch_ncr_issuer_rating_actions(
        transport=httpx.MockTransport(lambda _request: response),
        retrieved_at=NOW,
        max_response_bytes=100,
    )
    assert result.status is CreditRatingSourceStatus.UNAVAILABLE
    assert result.error_code is expected_code
    assert result.source is None
    assert result.records == ()
    assert result.warnings == ()


def test_fetch_maps_network_parser_and_redirect_failures_without_text() -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private network detail", request=request)

    network = fetch_ncr_issuer_rating_actions(
        transport=httpx.MockTransport(broken),
        retrieved_at=NOW,
    )
    parser = fetch_ncr_issuer_rating_actions(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"not the expected page",
            )
        ),
        retrieved_at=NOW,
    )
    redirect = fetch_ncr_issuer_rating_actions(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                302,
                headers={"location": "https://example.com/private"},
            )
        ),
        retrieved_at=NOW,
    )
    assert network.error_code is CreditRatingSourceErrorCode.NETWORK_ERROR
    assert parser.error_code is CreditRatingSourceErrorCode.SCHEMA_INVALID
    assert redirect.error_code is CreditRatingSourceErrorCode.HTTP_ERROR
    for result in (network, parser, redirect):
        serialized = result.model_dump_json()
        assert "private" not in serialized
        assert "example.com" not in serialized


@pytest.mark.parametrize(
    ("timeout_seconds", "max_response_bytes"),
    [
        (True, 100),
        (0, 100),
        (-1, 100),
        (float("nan"), 100),
        (float("inf"), 100),
        (10.01, 100),
        (1, True),
        (1, 0),
        (1, 2_000_001),
        (cast(float, "1"), 100),
    ],
)
def test_fetch_controls_are_bounded_and_fail_closed(
    timeout_seconds: float,
    max_response_bytes: int,
) -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"unused")

    result = fetch_ncr_issuer_rating_actions(
        transport=httpx.MockTransport(handler),
        retrieved_at=NOW,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
    )
    assert result.status is CreditRatingSourceStatus.UNAVAILABLE
    assert result.error_code is CreditRatingSourceErrorCode.SCHEMA_INVALID
    assert calls == 0


def test_streamed_response_size_is_bounded() -> None:
    result = fetch_ncr_issuer_rating_actions(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"x" * 101,
            )
        ),
        retrieved_at=NOW,
        max_response_bytes=100,
    )
    assert result.error_code is CreditRatingSourceErrorCode.RESPONSE_TOO_LARGE


def test_invalid_transport_object_fails_before_io() -> None:
    result = fetch_ncr_issuer_rating_actions(
        transport=cast(httpx.BaseTransport, object()),
        retrieved_at=NOW,
    )
    assert result.status is CreditRatingSourceStatus.UNAVAILABLE
    assert result.error_code is CreditRatingSourceErrorCode.SCHEMA_INVALID


def test_module_has_no_route_startup_or_write_surface() -> None:
    import omni_cio.market.ncr_rating_actions_v1 as module

    for forbidden in (
        "app",
        "router",
        "startup",
        "webhook",
        "create_order",
        "post_order",
        "cancel_order",
        "withdraw",
        "transfer",
    ):
        assert not hasattr(module, forbidden)
