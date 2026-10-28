"""Bounded RSS/Atom, discovery metadata and issuer report indexes."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json
import re
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

try:
    from .osint_catalogue import IntakeError, canonical_url, target_url, MAX_BODY
    from .osint_analysis import clean_text
except ImportError:
    from osint_catalogue import IntakeError, canonical_url, target_url, MAX_BODY
    from osint_analysis import clean_text


def timestamp(value: str | None) -> int | None:
    if not value:
        return None
    try:
        value = value.strip()
        if re.fullmatch(r"\d{8}T\d{6}Z", value):
            result = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        elif re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", value):
            result = datetime.strptime(value, "%d.%m.%Y").replace(tzinfo=timezone.utc)
        else:
            try:
                result = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                result = parsedate_to_datetime(value)
        return int(result.timestamp()) if result.utcoffset() is not None else None
    except (ValueError, TypeError, OverflowError, OSError):
        return None


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.ignored = [], [], []
        self.anchor = None
        self.nodes = 0

    def handle_starttag(self, tag, attrs):
        self.nodes += 1
        if self.nodes > 50000:
            raise IntakeError("osint_html_node_limit")
        if tag in {"script", "style", "nav", "footer", "header", "form", "noscript", "svg"}:
            self.ignored.append(tag)
        if self.ignored:
            return
        attrs = dict(attrs)
        if tag == "a":
            self.anchor = {"href": attrs.get("href", ""), "parts": [],
                "title": attrs.get("title", ""), "context": " ".join(self.parts[-25:])[-1000:]}
        if tag in {"p", "div", "tr", "br", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.ignored:
            self.ignored = self.ignored[:len(self.ignored) - 1 - self.ignored[::-1].index(tag)]
            return
        if self.ignored:
            return
        if tag == "a" and self.anchor is not None:
            item = self.anchor
            item["label"] = " ".join(item.pop("parts")) or item["title"]
            self.links.append(item)
            self.anchor = None

    def handle_data(self, data):
        if self.ignored:
            return
        text = data.strip()
        if text:
            self.parts.append(text)
            if self.anchor is not None:
                self.anchor["parts"].append(text)


def page(value: str) -> Page:
    result = Page()
    result.feed(value[:MAX_BODY])
    result.close()
    return result


def plain(value: str) -> str:
    return clean_text(" ".join(page(value).parts))


def _child(item, names):
    return next((element for element in item if element.tag.rsplit("}", 1)[-1] in names), None)


def _entry(item, source, now):
    title_node = _child(item, {"title"})
    title = plain(" ".join(title_node.itertext())) if title_node is not None else ""
    link = _child(item, {"link"})
    url = (link.attrib.get("href") or link.text or "").strip() if link is not None else ""
    if url.startswith("http://") and urlsplit(url).hostname in source.hosts:
        url = "https://" + url[7:]
    url = canonical_url(url)
    body = _child(item, {"description", "summary", "content", "encoded"})
    text = plain(" ".join(body.itertext())) if body is not None else title
    published = _child(item, {"pubDate", "published", "date"})
    at = timestamp(published.text) if published is not None else None
    if at is not None and at > now + 600:
        at = None
    if not title:
        raise IntakeError("osint_item_title_missing")
    return {"url": url, "title": title[:400], "text": text, "published_at": at,
            "publisher": source.publisher, "primary": source.primary and urlsplit(url).hostname in source.hosts, "kind": "news"}


def feed(raw: bytes, source, now: int) -> tuple[list[dict], dict]:
    if len(raw) > MAX_BODY or b"\0" in raw or re.search(br"<!DOCTYPE|<!ENTITY", raw, re.I):
        raise IntakeError("osint_xml_unsafe")
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        raise IntakeError("osint_feed_invalid") from None
    nodes = list(root.iter())
    if len(nodes) > 20000 or root.tag.rsplit("}", 1)[-1].lower() not in {"rss", "rdf", "feed"}:
        raise IntakeError("osint_feed_schema_invalid")
    entries = [item for item in nodes if item.tag.rsplit("}", 1)[-1] in {"item", "entry"}]
    rows, rejected = [], 0
    for item in entries[:500]:
        try:
            rows.append(_entry(item, source, now))
        except (IntakeError, ValueError):
            rejected += 1
    return rows, {"items_seen": len(entries), "rejected": rejected, "truncated": len(entries) > 500,
                  "coverage": "publisher_feed_window"}


def report_links(raw: bytes, source, base: str, now: int) -> tuple[list[dict], dict]:
    parsed = page(raw.decode("utf-8", errors="replace"))
    targets = {}
    for link in parsed.links:
        label = plain(link["label"])[:400]
        context = plain(link["context"])
        url = urljoin(base, link["href"])
        try:
            path = urlsplit(url).path.lower()
        except ValueError:
            continue
        years = [int(value) for value in re.findall(r"(?<!\d)20\d{2}(?!\d)", label + " " + path)]
        current_year = datetime.fromtimestamp(now, timezone.utc).year
        if years and max(years) < current_year - 4:
            continue
        kind = "pdf" if path.endswith(".pdf") or re.fullmatch(r"/files/\d+", path) else "index"
        terms = label + " " + context[-650:]
        if kind == "pdf":
            if not re.search(r"отч[её]тност|МСФО|РСБУ|financial.statement|IFRS", terms, re.I):
                continue
            if re.search(r"презентац|presentat|транскрипт|transcript|датабук|databook", label, re.I):
                continue
        elif not re.search(r"/20\d{2}/?$", path):
            continue
        try:
            url = target_url(source, url, kind)
        except (IntakeError, ValueError):
            continue
        dates = re.findall(r"\b\d{2}\.\d{2}\.20\d{2}\b", label)
        published = timestamp(dates[-1]) if dates else None
        if published and published > now + 600:
            published = None
        targets[url] = {"url": url, "kind": kind, "title": label or source.title,
                        "published_at": published, "context": context[-1000:]}
    ordered = sorted(targets.values(), key=lambda row: (row["published_at"] or 0, row["url"]), reverse=True)
    return ordered[:120], {"items_seen": len(targets), "truncated": len(targets) > 120,
                          "coverage": "approved_issuer_index", "empty_index": not targets}


def discovery(raw: bytes, now: int) -> tuple[list[dict], dict]:
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise IntakeError("osint_discovery_invalid") from None
    if not isinstance(value, dict) or not isinstance(value.get("articles"), list):
        raise IntakeError("osint_discovery_schema_invalid")
    entries = value["articles"]
    rows, rejected = [], 0
    for item in entries[:250]:
        try:
            url = canonical_url(item["url"])
            title = clean_text(item["title"], 400)
            seen = timestamp(item.get("seendate"))
            if not title or seen is None or seen > now + 600:
                raise IntakeError("osint_discovery_item_invalid")
            rows.append({"url": url, "title": title, "text": title, "published_at": None,
                "discovered_at": seen, "publisher": urlsplit(url).hostname, "primary": False, "kind": "news"})
        except (ValueError, KeyError, TypeError):
            rejected += 1
    return rows, {"items_seen": len(entries), "rejected": rejected, "truncated": len(entries) >= 250,
                  "coverage": "discovery_metadata_only", "publication_dates_known": False}
