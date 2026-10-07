"""Public Bank of Russia RSS headlines; no invented news or private credentials."""

from __future__ import annotations

import hashlib
import http.client
import re
import threading
import time
import xml.etree.ElementTree as ET
from contextlib import closing
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_SOURCE_HOST = "www.cbr.ru"
_SOURCE_URL = f"https://{_SOURCE_HOST}/rss/eventrss"
_MAX_BYTES = 512_000


class NewsUnavailable(RuntimeError):
    """The official source is unavailable or its content is not a valid feed."""


class NewsNotFound(LookupError):
    """The requested identifier is not in the source-confirmed feed."""


class _SourceText(HTMLParser):
    """Bounded plain-text extraction; source markup is never returned as HTML."""
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored: list[str] = []
        self.body = False
        self.length = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "body":
            self.body = True
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header", "form"}:
            self.ignored.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "body":
            self.body = False
        if self.ignored and tag == self.ignored[-1]:
            self.ignored.pop()

    def handle_data(self, data: str) -> None:
        if self.body and not self.ignored and self.length < 32000:
            text = " ".join(data.split())
            if text:
                self.parts.append(text[:32000 - self.length])
                self.length += len(text)


def source_page_text(raw: bytes) -> tuple[str, bool]:
    if len(raw) > _MAX_BYTES:
        raise NewsUnavailable("news_source_too_large")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NewsUnavailable("news_source_encoding_invalid") from exc
    if "\x00" in text:
        raise NewsUnavailable("news_source_invalid")
    parser = _SourceText()
    parser.feed(text)
    parser.close()
    extracted = "\n".join(parser.parts)
    if len(extracted) < 40:
        raise NewsUnavailable("news_source_text_unavailable")
    return extracted[:16000], len(extracted) > 16000


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
                    or parsed.hostname not in {"cbr.ru", _SOURCE_HOST}
                    or parsed.username is not None or parsed.password is not None
                    or parsed.port is not None or not title or len(title) > 500
                    or published.tzinfo is None or published > fetched_at):
                continue
        except (ValueError, TypeError, IndexError):
            continue
        # The source links sometimes use HTTP; the canonical public site has TLS.
        url = urlunsplit(("https", _SOURCE_HOST, parsed.path, parsed.query, ""))
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
        self._reading = threading.BoundedSemaphore(2)
        self._article_lock = threading.Lock()
        self._articles: dict[str, tuple[float, dict[str, Any]]] = {}

    def search(self, query: str, *, limit: int = 10) -> dict[str, Any]:
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200 or not 1 <= limit <= 20:
            raise ValueError("news_query_invalid")
        payload = self.headlines()
        terms = query.casefold().split()
        matches = [item for item in payload["items"]
                   if all(term in item["title"].casefold() for term in terms)]
        return {"items": matches[:limit], "total": len(matches), "truncated": len(matches) > limit,
                "scope": "current_cbr_feed", "web_search": False,
                "fetched_at": payload["fetched_at"], "freshness": payload["freshness"]}

    def read_source(self, source_id: str) -> dict[str, Any]:
        if not isinstance(source_id, str) or re.fullmatch(r"[0-9a-f]{64}", source_id) is None:
            raise ValueError("news_source_id_invalid")
        with self._article_lock:
            cached = self._articles.get(source_id)
        if cached and time.monotonic() < cached[0]:
            return {**cached[1], "freshness": "cached"}
        feed = self.headlines()
        item = next((row for row in feed["items"] if row["id"] == source_id), None)
        if item is None:
            raise NewsNotFound("news_source_not_found")
        parsed = urlsplit(item["url"])
        if (parsed.scheme != "https" or parsed.hostname != _SOURCE_HOST or parsed.port
                or parsed.username or parsed.password or parsed.fragment
                or not parsed.path.startswith("/")
                or any(ord(char) < 33 for char in item["url"])):
            raise NewsUnavailable("news_source_invalid")
        if not self._reading.acquire(blocking=False):
            raise NewsUnavailable("news_source_busy")
        try:
            with closing(http.client.HTTPSConnection(_SOURCE_HOST, timeout=6)) as conn:
                path = parsed.path + ("?" + parsed.query if parsed.query else "")
                conn.request("GET", path, headers={"Accept": "text/html",
                             "User-Agent": "OMNICIO/1.3 (+https://omnicio.ru)"})
                response = conn.getresponse()
                if response.status != 200:
                    raise NewsUnavailable("news_source_unavailable")
                content_type = response.getheader("Content-Type", "").split(";", 1)[0].lower()
                if content_type not in {"text/html", "application/xhtml+xml"}:
                    raise NewsUnavailable("news_source_type_invalid")
                raw = response.read(_MAX_BYTES + 1)
            content, truncated = source_page_text(raw)
            result = {**item, "content": content, "truncated": truncated,
                      "scope": "official_page_text", "web_search": False,
                      "sha256": hashlib.sha256(raw).hexdigest(),
                      "fetched_at": datetime.now(UTC).isoformat(), "freshness": "fresh"}
            with self._article_lock:
                if len(self._articles) >= 20:
                    del self._articles[next(iter(self._articles))]
                self._articles[source_id] = (time.monotonic() + 300, result)
            return result
        except (OSError, http.client.HTTPException) as exc:
            raise NewsUnavailable("news_source_unavailable") from exc
        finally:
            self._reading.release()

    def headlines(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._cached is not None and now < self._expires:
            return self._cached
        if now < self._retry_after or not self._lock.acquire(blocking=False):
            return self._fallback()
        try:
            try:
                with closing(http.client.HTTPSConnection(_SOURCE_HOST, timeout=6)) as conn:
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
