"""Official-news input, immutable source identity, and cache freshness boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock, patch
from xml.sax.saxutils import escape

import pytest

from omnicio.news import NewsClient, NewsUnavailable, parse_news

NOW = datetime(2026, 10, 6, 12, tzinfo=UTC)


def item(
    *,
    title: str = "Публикация Банка России",
    link: str = "https://www.cbr.ru/press/event/1",
    published: str = "Mon, 05 Oct 2026 12:00:00 GMT",
) -> str:
    return (
        f"<item><title>{escape(title)}</title><link>{escape(link)}</link>"
        f"<pubDate>{escape(published)}</pubDate></item>"
    )


def feed(*items: str) -> bytes:
    return (
        "<?xml version='1.0' encoding='UTF-8'?><rss><channel>" + "".join(items) + "</channel></rss>"
    ).encode()


def test_news_keeps_real_dates_sorts_deduplicates_and_canonicalizes_source_https() -> None:
    payload = parse_news(
        feed(
            item(link="http://cbr.ru/press/event/1"),
            item(link="https://www.cbr.ru/press/event/1", title="Duplicate URL"),
            item(
                link="https://cbr.ru/press/event/2?id=1",
                title="Свежая публикация",
                published="Tue, 06 Oct 2026 14:00:00 +0300",
            ),
            item(link="https://www.cbr.ru/future", published="Wed, 07 Oct 2026 12:00:00 GMT"),
        ),
        fetched_at=NOW,
    )
    assert len(payload["items"]) == 2
    newest, older = payload["items"]
    assert newest["title"] == "Свежая публикация"
    assert newest["published_at"] == "2026-10-06T11:00:00+00:00"
    assert newest["url"] == "https://www.cbr.ru/press/event/2?id=1"
    assert older["url"] == "https://www.cbr.ru/press/event/1"
    assert newest["id"] != older["id"] and len(newest["id"]) == 64
    assert payload["fetched_at"] == NOW.isoformat()
    assert payload["freshness"] == "fresh"


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://cbr.ru.evil.invalid/path",
        "https://cbr.ru@evil.invalid/path",
        "https://user:secret@www.cbr.ru/path",
        "https://www.cbr.ru:443/path",
        "//www.cbr.ru/path",
        "file:///tmp/news",
        "https://127.0.0.1/news",
        "https://www.cbr.ru:invalid/path",
    ],
)
def test_news_rejects_untrusted_link_instead_of_rewriting_its_authority(url: str) -> None:
    document = feed(item(link=url))
    with pytest.raises(NewsUnavailable, match="empty"):
        parse_news(document, fetched_at=NOW)


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
def test_news_forbids_dtd_and_entities_in_every_supported_xml_encoding(encoding: str) -> None:
    xml = (
        f'<?xml version="1.0" encoding="{encoding}"?>'
        '<!DOCTYPE rss [<!ENTITY headline "Expanded internal entity">]>'
        "<rss><channel><item><title>&headline;</title>"
        "<link>https://www.cbr.ru/press/event/1</link>"
        "<pubDate>Mon, 05 Oct 2026 12:00:00 GMT</pubDate></item></channel></rss>"
    )
    document = xml.encode(encoding)
    with pytest.raises(NewsUnavailable, match="invalid"):
        parse_news(document, fetched_at=NOW)


@pytest.mark.parametrize("payload", [b"x" * 512001, b"<rss>", b"<html/>", b"<rss><channel/></rss>"])
def test_news_malformed_empty_and_oversized_feed_fails_without_invented_headlines(
    payload: bytes,
) -> None:
    with pytest.raises(NewsUnavailable):
        parse_news(payload, fetched_at=NOW)


def test_news_drops_unparseable_or_timezone_unknown_dates_and_bounds_items() -> None:
    payload = parse_news(
        feed(
            item(link="https://www.cbr.ru/unknown", published="not a date"),
            item(link="https://www.cbr.ru/naive", published="Mon, 05 Oct 2026 12:00:00"),
            *(item(link=f"https://www.cbr.ru/press/event/{index}") for index in range(120)),
        ),
        fetched_at=NOW,
    )
    assert len(payload["items"]) == 20
    assert all(
        row["url"] not in {"https://www.cbr.ru/unknown", "https://www.cbr.ru/naive"}
        for row in payload["items"]
    )


def test_news_cache_expiration_outage_retry_and_recovery_are_explicit() -> None:
    clock = [0.0]
    good = Mock(status=200, read=Mock(return_value=feed(item())))
    outage = Mock(status=503)
    recovered = Mock(status=200, read=Mock(return_value=feed(item(title="После обновления"))))
    connection = Mock()
    connection.getresponse.side_effect = [good, outage, recovered]
    client = NewsClient()
    with (
        patch("omnicio.news.time.monotonic", side_effect=lambda: clock[0]),
        patch(
            "omnicio.news.http.client.HTTPSConnection",
            return_value=connection,
        ) as factory,
    ):
        first = client.headlines()
        assert first["freshness"] == "fresh"
        clock[0] = 299
        assert client.headlines() == first
        assert factory.call_count == 1
        clock[0] = 300
        stale = client.headlines()
        assert stale["freshness"] == "cached"
        assert stale["fetched_at"] == first["fetched_at"]
        clock[0] = 359
        assert client.headlines()["freshness"] == "cached"
        assert factory.call_count == 2
        clock[0] = 360
        assert client.headlines()["items"][0]["title"] == "После обновления"
        assert factory.call_count == 3
    assert first["freshness"] == "fresh"
    good.read.assert_called_once_with(512001)
    assert all(call.args == ("www.cbr.ru",) for call in factory.call_args_list)
    assert all(call.args == ("GET", "/rss/eventrss") for call in connection.request.call_args_list)
    assert not any(
        "Authorization" in call.kwargs["headers"] for call in connection.request.call_args_list
    )


def test_news_redirect_is_not_followed_and_failure_backoff_preserves_no_data() -> None:
    response = Mock(status=302)
    connection = Mock()
    connection.getresponse.return_value = response
    client = NewsClient()
    with (
        patch("omnicio.news.time.monotonic", return_value=100),
        patch(
            "omnicio.news.http.client.HTTPSConnection",
            return_value=connection,
        ) as factory,
    ):
        for _ in range(2):
            with pytest.raises(NewsUnavailable):
                client.headlines()
    factory.assert_called_once()
    connection.request.assert_called_once()
    response.read.assert_not_called()
