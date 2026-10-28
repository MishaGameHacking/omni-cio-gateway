"""Reviewed public investment sources; no credentials, dump sites or private feeds."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import ipaddress
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

USER_AGENT = "AnalystAIResearch/1.0 (+https://github.com/MishaGameHacking/omni-cio-gateway)"
MOEX_HOSTS = ("www.moex.com", "moex.com")
MOEX_RSS_DOCUMENTATION = "https://www.moex.com/a40"
MAX_TEXT = 240_000
MAX_BODY = 2 * 1024 * 1024
MAX_PDF = 12 * 1024 * 1024


class IntakeError(ValueError):
    """Only stable codes, never remote content or credentials."""


@dataclass(frozen=True)
class Source:
    id: str
    title: str
    url: str
    kind: str
    publisher: str
    hosts: tuple[str, ...]
    interval: int
    documentation: str
    issuer: str | None = None
    permission: str = "public_publisher_material"
    primary: bool = True


SOURCES = (
    Source("moex_news", "Новости Московской биржи", "https://www.moex.com/export/news.aspx?cat=100",
           "rss", "moex", MOEX_HOSTS, 600, MOEX_RSS_DOCUMENTATION,
           permission="publisher_rss_headlines_and_annotations"),
    Source("moex_listing", "Новости листинга", "https://www.moex.com/export/news.aspx?cat=104",
           "rss", "moex", MOEX_HOSTS, 900, MOEX_RSS_DOCUMENTATION,
           permission="publisher_rss_headlines_and_annotations"),
    Source("moex_risk", "Риск-параметры биржи", "https://www.moex.com/export/news.aspx?cat=122",
           "rss", "moex", MOEX_HOSTS, 900, MOEX_RSS_DOCUMENTATION,
           permission="publisher_rss_headlines_and_annotations"),
    Source("cbr_press", "Пресс-релизы Банка России", "https://www.cbr.ru/rss/RssPress",
           "rss", "cbr", ("www.cbr.ru", "cbr.ru"), 900, "https://cbr.ru/development/RSS/",
           permission="publisher_rss"),
    Source("moex_reports", "Отчётность Московской биржи",
           "https://www.moex.com/o-birzhe/finansovaya-otchetnost/msfo",
           "index", "moex", (*MOEX_HOSTS, "fs.moex.com"), 21600,
           "https://www.moex.com/o-birzhe/finansovaya-otchetnost/msfo", "Московская Биржа"),
    Source("nornickel_reports", "Отчётность Норникеля", "https://nornickel.ru/investors/",
           "index", "nornickel", ("nornickel.ru", "www.nornickel.ru"), 21600,
           "https://nornickel.ru/investors/reports-and-results/current-results/", "Норникель"),
    Source("gazprom_reports", "Отчётность Газпрома", "https://www.gazprom.ru/investors/disclosure/reports/",
           "index", "gazprom", ("www.gazprom.ru", "gazprom.ru"), 21600,
           "https://www.gazprom.ru/investors/disclosure/reports/", "Газпром"),
    Source("gdelt_finance", "Поиск публичных инвестиционных публикаций",
           "https://api.gdeltproject.org/api/v2/doc/doc", "gdelt", "gdelt-discovery",
           ("api.gdeltproject.org",), 1800, "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/",
           permission="metadata_discovery_only", primary=False),
)
BY_ID = {source.id: source for source in SOURCES}
GDELT_QUERY = '(MOEX OR "Moscow Exchange" OR Gazprom OR Sberbank OR Nornickel OR "московская биржа")'


def catalogue() -> list[dict]:
    return [asdict(source) for source in SOURCES]


def canonical_url(value: str, hosts: tuple[str, ...] | None = None) -> str:
    if not isinstance(value, str) or not value or len(value) > 2048 or re.search(r"[\x00-\x20\\]", value):
        raise IntakeError("osint_url_invalid")
    try:
        url = urlsplit(value)
        host = (url.hostname or "").encode("idna").decode().lower()
        port = url.port
    except ValueError:
        raise IntakeError("osint_url_invalid") from None
    if url.scheme != "https" or not host or url.username or url.password or port not in (None, 443):
        raise IntakeError("osint_url_invalid")
    if hosts is not None and host not in hosts:
        raise IntakeError("osint_host_not_approved")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise IntakeError("osint_literal_address_denied")
    if "." not in host or host.endswith((".local", ".internal", ".onion")):
        raise IntakeError("osint_host_not_public")
    query = clean_query(url.query)
    return urlunsplit(("https", host, url.path or "/", query, ""))


def clean_query(query: str) -> str:
    try:
        pairs = parse_qsl(query, keep_blank_values=True, max_num_fields=40)
    except ValueError:
        raise IntakeError("osint_url_invalid") from None
    if any(re.search(r"password|secret|access_token|authorization|api[_-]?key", key, re.I) for key, _ in pairs):
        raise IntakeError("osint_credential_url_denied")
    pairs = [(key, value) for key, value in pairs
             if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}]
    return urlencode(sorted(pairs))


def target_url(source: Source, url: str, kind: str) -> str:
    result = canonical_url(url, source.hosts)
    path = urlsplit(result).path.lower()
    if kind == "pdf" and not (path.endswith(".pdf") or re.fullmatch(r"/files/\d+", path)):
        raise IntakeError("osint_document_path_denied")
    if kind == "index" and result != canonical_url(source.url, source.hosts):
        prefix = urlsplit(source.url).path.rstrip("/") + "/"
        if not path.startswith(prefix) or not re.search(r"/20\d{2}/?$", path):
            raise IntakeError("osint_index_path_denied")
    return result
