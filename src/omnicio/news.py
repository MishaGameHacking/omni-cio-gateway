"""Public Bank of Russia RSS headlines; no invented news or private credentials."""

from __future__ import annotations

import hashlib
import http.client
import threading
import time
import xml.etree.ElementTree as ET
from contextlib import closing
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any
from urllib.parse import urlsplit

_SOURCE_URL = "https://www.cbr.ru/rss/eventrss"
_MAX_BYTES = 512_000


class NewsUnavailable(RuntimeError):
    """The official source is unavailable or its content is not a valid feed."""


def parse_news(raw: bytes, *, fetched_at: datetime) -> dict[str, Any]:
    if len(raw) > _MAX_BYTES:
        raise NewsUnavailable("news_feed_invalid")
    try:
        decoded = raw.decode("utf-8-sig")
        if ("\x00" in decoded or "<!DOCTYPE" in decoded.upper()
                or "<!ENTITY" in decoded.upper()):
            raise NewsUnavailable("news_feed_invalid")
        root = ET.fromstring(decoded)
    except (ET.ParseError, UnicodeDecodeError) as exc:
        raise NewsUnavailable("news_feed_invalid") from exc
    if root.tag != "rss":
        raise NewsUnavailable("news_feed_invalid")
    items = []
    seen = set()
    for item in root.findall("./channel/item")[:100]:
        title = " ".join(unescape(item.findtext("title", "")).split())
        link = item.findtext("link", "").strip()
        try:
            parsed = urlsplit(link)
            published = parsedate_to_datetime(item.findtext("pubDate", ""))
            if (parsed.scheme not in {"https", "http"}
                    or parsed.hostname not in {"cbr.ru", "www.cbr.ru"}
                    or parsed.username is not None or parsed.password is not None
                    or parsed.port is not None or not title or len(title) > 500
                    or published.tzinfo is None or published > fetched_at):
                continue
        except (ValueError, TypeError, IndexError):
            continue
        # The source links sometimes use HTTP; the canonical public site has TLS.
        url = "https://www.cbr.ru" + parsed.path
        if parsed.query:
            url += "?" + parsed.query
        identity = hashlib.sha256(url.encode()).hexdigest()
        if identity in seen:
            continue
        seen.add(identity)
        items.append({
            "id": identity, "title": title, "url": url,
            "published_at": published.astimezone(UTC).isoformat(),
            "source": "Банк России", "category": "market",
        })
    if not items:
        raise NewsUnavailable("news_feed_empty")
    items.sort(key=lambda row: row["published_at"], reverse=True)
    return {
        "items": items[:20], "source_url": _SOURCE_URL,
        "fetched_at": fetched_at.isoformat(), "freshness": "fresh",
    }


class NewsClient:
    def __init__(self) -> None:
        self._cached: dict[str, Any] | None = None
        self._expires = 0.0
        self._retry_after = 0.0
        self._lock = threading.Lock()

    def headlines(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._cached is not None and now < self._expires:
            return self._cached
        if now < self._retry_after or not self._lock.acquire(blocking=False):
            return self._fallback()
        try:
            try:
                with closing(http.client.HTTPSConnection("www.cbr.ru", timeout=6)) as conn:
                    conn.request("GET", "/rss/eventrss", headers={
                        "Accept": "application/rss+xml,application/xml,text/xml",
                        "User-Agent": "OMNICIO/1.0 (+https://omnicio.ru)",
                    })
                    response = conn.getresponse()
                    if response.status != 200:
                        raise NewsUnavailable("news_source_unavailable")
                    raw = response.read(_MAX_BYTES + 1)
                payload = parse_news(raw, fetched_at=datetime.now(UTC))
            except (OSError, http.client.HTTPException, NewsUnavailable):
                self._retry_after = time.monotonic() + 60
                return self._fallback()
            self._cached = payload
            self._expires = time.monotonic() + 300
            self._retry_after = 0
            return payload
        finally:
            self._lock.release()

    def _fallback(self) -> dict[str, Any]:
        if self._cached is None:
            raise NewsUnavailable("news_source_unavailable")
        return {**self._cached, "freshness": "cached"}
