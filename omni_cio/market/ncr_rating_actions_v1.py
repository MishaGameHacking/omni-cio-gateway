from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
import math
import re
from typing import Final
from urllib.parse import urljoin, urlparse

import httpx
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


NCR_RATING_ACTIONS_ENDPOINT: Final = "https://ratings.ru/ratings/press-releases/"
NCR_RATING_ACTIONS_PROVIDER: Final = "NCR"
NCR_RATING_ACTIONS_SOURCE_ID: Final = "NCR.press_releases.issuer_rating_actions"
DEFAULT_NCR_TIMEOUT_SECONDS: Final = 10.0
DEFAULT_NCR_MAX_RESPONSE_BYTES: Final = 2_000_000
MAX_NCR_RECORDS: Final = 30

_ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
_ALLOWED_RELEASE_HOSTS = frozenset({"ratings.ru", "www.ratings.ru"})
_RELEASE_SLUG = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,126}[A-Za-z0-9])?"
_ALLOWED_RELEASE_PATH = re.compile(
    r"^/ratings/press-releases/"
    rf"(?P<slug>{_RELEASE_SLUG})-[Rr][Aa]-"
    r"(?P<day>0[1-9]|[12][0-9]|3[01])"
    r"(?P<month>0[1-9]|1[0-2])(?P<year>[0-9]{2})/$"
)
_DATE_PATTERN = re.compile(
    r"^(?P<day>0[1-9]|[12][0-9]|3[01])\."
    r"(?P<month>0[1-9]|1[0-2])\."
    r"(?P<year>20[0-9]{2})$"
)
_RATING_TOKEN = r"(?:[AАBВCС]{1,3}[+-]?\.[RР][UУ]|[DД])"
_RATING_IN_TEXT = re.compile(
    rf"(?<![A-Za-zА-Яа-я0-9]){_RATING_TOKEN}"
    r"(?![A-Za-zА-Яа-я0-9])",
    re.IGNORECASE,
)
_ASSIGN_PATTERN = re.compile(
    rf"^НКР присвоило (?P<subject>.+?) кредитный рейтинг"
    rf"(?: на уровне)? (?P<rating>{_RATING_TOKEN})(?P<tail>.*)$",
    re.IGNORECASE,
)
_AFFIRM_PATTERN = re.compile(
    rf"^НКР подтвердило кредитный рейтинг (?P<subject>.+?) "
    rf"на уровне (?P<rating>{_RATING_TOKEN})(?P<tail>.*)$",
    re.IGNORECASE,
)
_UP_DOWN_PATTERN = re.compile(
    rf"^НКР (?P<verb>повысило|снизило|понизило) кредитный рейтинг "
    rf"(?P<subject>.+?) с (?P<previous>{_RATING_TOKEN}) "
    rf"до (?P<rating>{_RATING_TOKEN})(?P<tail>.*)$",
    re.IGNORECASE,
)
_WITHDRAW_PATTERN = re.compile(
    r"^НКР отозвало кредитный рейтинг (?P<subject>.+?)"
    r"(?: и прогноз по нему)?(?: без подтверждения)?"
    r"(?: в связи с .+)?$",
    re.IGNORECASE,
)
_UNDER_REVISION_TOKEN = (
    r"рейтинг на пересмотре (?:"
    r"с возможностью (?:повышения|понижения)"
    r"|(?:—|-) неопредел(?:ё|е)нный прогноз"
    r")"
)
_OUTLOOK_TAIL = re.compile(
    r"^(?:"
    r"с(?:о)? (?P<with>стабильным|позитивным|негативным|"
    r"развивающимся) прогнозом"
    r"|, прогноз(?: по кредитному рейтингу)? "
    r"(?:(?:—|-)|измен(?:ё|е)н на) "
    r"(?P<changed>стабильный|позитивный|негативный|"
    r"развивающийся|неопредел(?:ё|е)нный|"
    rf"{_UNDER_REVISION_TOKEN}|"
    rf"«{_UNDER_REVISION_TOKEN}»|\"{_UNDER_REVISION_TOKEN}\")"
    r")$",
    re.IGNORECASE,
)
_ACTION_WORDS = (
    "ПРИСВОИЛО",
    "ПОДТВЕРДИЛО",
    "ПОВЫСИЛО",
    "СНИЗИЛО",
    "ПОНИЗИЛО",
    "ОТОЗВАЛО",
)
_UNSUPPORTED_COMPLEX = (
    "КРЕДИТНЫЕ РЕЙТИНГИ",
    "ОЖИДАЕМЫЙ КРЕДИТНЫЙ РЕЙТИНГ",
    "ОЖИДАЕМЫЕ КРЕДИТНЫЕ РЕЙТИНГИ",
    "ПОВЫСИЛО И ОТОЗВАЛО",
    "ПОНИЗИЛО И ОТОЗВАЛО",
    "СНИЗИЛО И ОТОЗВАЛО",
)
_ISSUE_MARKERS = (
    " ОБЛИГАЦ",
    " ВЫПУСК",
    " ВЫПУСКУ",
    " ВЫПУСКАМ",
    " ЭМИССИ",
    " СЕРИИ ",
    " СЕРИЙ ",
    " СЕРИЯ ",
    " ТРАНШ",
    " ISIN",
    " ДОЛГОВОГО ОБЯЗАТЕЛЬСТВА",
)
_CONFUSABLES = str.maketrans(
    {
        "А": "A",
        "а": "A",
        "В": "B",
        "в": "B",
        "С": "C",
        "с": "C",
        "Д": "D",
        "д": "D",
        "Р": "R",
        "р": "R",
        "У": "U",
        "у": "U",
    }
)
_SUPPORTED_RATINGS = frozenset(
    {
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
    }
)
_MAX_CLOCK_SKEW = timedelta(days=1)
_MAX_DATE_LOOKAHEAD_EVENTS = 6


class NcrRatingActionsSourceError(ValueError):
    """The fixed official NCR action source cannot be handled safely."""


@dataclass(frozen=True)
class _HtmlEvent:
    text: str
    href: str | None


class _VisibleLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: list[_HtmlEvent] = []
        self._anchor_open = False
        self._href: str | None = None
        self._anchor_chunks: list[str] = []
        self._ignored_tags: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            self._ignored_tags.append(lowered)
            return
        if lowered == "a" and not self._ignored_tags:
            if self._anchor_open:
                raise NcrRatingActionsSourceError(
                    CreditRatingSourceErrorCode.HTML_INVALID.value
                )
            href_values = [value for name, value in attrs if name.lower() == "href"]
            if len(href_values) > 1:
                raise NcrRatingActionsSourceError(
                    CreditRatingSourceErrorCode.HTML_INVALID.value
                )
            self._anchor_open = True
            self._href = (href_values[0] if href_values else "") or ""
            self._anchor_chunks = []

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            if not self._ignored_tags or self._ignored_tags[-1] != lowered:
                raise NcrRatingActionsSourceError(
                    CreditRatingSourceErrorCode.HTML_INVALID.value
                )
            self._ignored_tags.pop()
            return
        if lowered == "a" and not self._ignored_tags:
            if not self._anchor_open:
                raise NcrRatingActionsSourceError(
                    CreditRatingSourceErrorCode.HTML_INVALID.value
                )
            text = _normalize_text(" ".join(self._anchor_chunks))
            if text:
                self.events.append(_HtmlEvent(text=text, href=self._href or ""))
            self._anchor_open = False
            self._href = None
            self._anchor_chunks = []

    def handle_data(self, data: str) -> None:
        if self._ignored_tags:
            return
        text = _normalize_text(data)
        if not text:
            return
        if self._anchor_open:
            self._anchor_chunks.append(text)
        else:
            self.events.append(_HtmlEvent(text=text, href=None))

    def error(self, message: str) -> None:
        raise NcrRatingActionsSourceError(message)


def _normalize_text(value: str) -> str:
    return " ".join(
        value.replace("\xa0", " ").replace("\u2011", "-").replace("\u2013", "-").split()
    )


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
        )
    return result.astimezone(timezone.utc)


def _release_match(href: str) -> tuple[re.Match[str], str]:
    if not isinstance(href, str) or not href.strip():
        raise NcrRatingActionsSourceError(CreditRatingSourceErrorCode.URL_INVALID.value)
    joined = urljoin(NCR_RATING_ACTIONS_ENDPOINT, href.strip())
    parsed = urlparse(joined)
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() not in _ALLOWED_RELEASE_HOSTS
        or parsed.query
        or parsed.fragment
    ):
        raise NcrRatingActionsSourceError(CreditRatingSourceErrorCode.URL_INVALID.value)
    match = _ALLOWED_RELEASE_PATH.fullmatch(parsed.path)
    if match is None:
        raise NcrRatingActionsSourceError(CreditRatingSourceErrorCode.URL_INVALID.value)
    try:
        date(
            2000 + int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError as exc:
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.URL_INVALID.value
        ) from exc
    canonical = (
        "https://ratings.ru/ratings/press-releases/"
        f"{match.group('slug')}-RA-"
        f"{match.group('day')}{match.group('month')}{match.group('year')}/"
    )
    return match, canonical


def _canonical_release_url(href: str) -> str:
    return _release_match(href)[1]


def _parse_date(text: str, *, retrieved_at: datetime) -> date:
    match = _DATE_PATTERN.fullmatch(text)
    if match is None:
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
        )
    try:
        parsed = date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError as exc:
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
        ) from exc
    if parsed > (retrieved_at + _MAX_CLOCK_SKEW).date():
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
        )
    return parsed


def _list_scope(events: tuple[_HtmlEvent, ...]) -> tuple[_HtmlEvent, ...]:
    header = next(
        (
            index
            for index, event in enumerate(events)
            if event.href is None and event.text == "Название"
        ),
        None,
    )
    if header is None:
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.SCHEMA_INVALID.value
        )
    nearby_headers = {
        event.text for event in events[header : header + 8] if event.href is None
    }
    if not {"Название", "Сектор", "Дата"}.issubset(nearby_headers):
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.SCHEMA_INVALID.value
        )
    return events[header + 1 :]


def _looks_like_release_href(value: str | None) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    parsed = urlparse(urljoin(NCR_RATING_ACTIONS_ENDPOINT, value.strip()))
    return (
        parsed.scheme == "https"
        and parsed.netloc.lower() in _ALLOWED_RELEASE_HOSTS
        and _ALLOWED_RELEASE_PATH.fullmatch(parsed.path) is not None
    )


def _find_publication_date(
    events: tuple[_HtmlEvent, ...],
    *,
    index: int,
    release_url: str,
    retrieved_at: datetime,
) -> date:
    stop = min(len(events), index + 1 + _MAX_DATE_LOOKAHEAD_EVENTS)
    for candidate in events[index + 1 : stop]:
        if _DATE_PATTERN.fullmatch(candidate.text) is not None:
            if candidate.href is not None:
                candidate_release_url = _canonical_release_url(candidate.href)
                if candidate_release_url != release_url:
                    raise NcrRatingActionsSourceError(
                        CreditRatingSourceErrorCode.IDENTITY_INVALID.value
                    )
            return _parse_date(candidate.text, retrieved_at=retrieved_at)
        if _looks_like_release_href(candidate.href):
            raise NcrRatingActionsSourceError(
                CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
            )
    raise NcrRatingActionsSourceError(
        CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
    )


def _normalize_rating(value: str) -> str:
    translated = _normalize_text(value).translate(_CONFUSABLES)
    if translated.upper() == "D":
        return "D"
    match = re.fullmatch(r"([ABC]{1,3}[+-]?)\.RU", translated.upper())
    if match is None:
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.RATING_INVALID.value
        )
    result = f"{match.group(1)}.ru"
    if result not in _SUPPORTED_RATINGS:
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.RATING_INVALID.value
        )
    return result


def _normalize_outlook(tail: str) -> CreditRatingOutlook | None:
    normalized = _normalize_text(tail)
    if not normalized:
        return None
    match = _OUTLOOK_TAIL.fullmatch(normalized)
    if match is None:
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.OUTLOOK_INVALID.value
        )
    value = (match.group("with") or match.group("changed")).strip('«»" ')
    root = value.lower()
    if root.startswith("стабиль"):
        return CreditRatingOutlook.STABLE
    if root.startswith("позитив"):
        return CreditRatingOutlook.POSITIVE
    if root.startswith("негатив"):
        return CreditRatingOutlook.NEGATIVE
    if root.startswith("развива"):
        return CreditRatingOutlook.DEVELOPING
    if root.startswith("неопредел") or root.startswith("рейтинг на пересмотре"):
        return CreditRatingOutlook.UNDER_REVISION
    raise NcrRatingActionsSourceError(CreditRatingSourceErrorCode.OUTLOOK_INVALID.value)


def _require_simple_subject(value: str) -> str:
    result = _normalize_text(value.strip(" ,.;"))
    upper = f" {result.upper()} "
    if (
        not result
        or len(result) > 256
        or any(marker in upper for marker in _ISSUE_MARKERS)
        or _RATING_IN_TEXT.search(result)
    ):
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.IDENTITY_INVALID.value
        )
    return result


def _is_action_title(value: str) -> bool:
    upper = _normalize_text(value).upper()
    return upper.startswith("НКР ") and any(word in upper for word in _ACTION_WORDS)


def _unsupported_title(value: str) -> bool:
    upper = f" {_normalize_text(value).upper()} "
    return any(marker in upper for marker in (*_UNSUPPORTED_COMPLEX, *_ISSUE_MARKERS))


def _parse_action_title(
    title: str,
) -> tuple[str, str | None, RatingAction, CreditRatingOutlook | None] | None:
    normalized = _normalize_text(title)
    if not _is_action_title(normalized):
        return None
    if _unsupported_title(normalized):
        return None
    if "КРЕДИТНЫЙ РЕЙТИНГ" not in normalized.upper():
        return None

    match = _ASSIGN_PATTERN.fullmatch(normalized)
    if match is not None:
        return (
            _require_simple_subject(match.group("subject")),
            _normalize_rating(match.group("rating")),
            RatingAction.ASSIGNED,
            _normalize_outlook(match.group("tail")),
        )

    match = _AFFIRM_PATTERN.fullmatch(normalized)
    if match is not None:
        return (
            _require_simple_subject(match.group("subject")),
            _normalize_rating(match.group("rating")),
            RatingAction.AFFIRMED,
            _normalize_outlook(match.group("tail")),
        )

    match = _UP_DOWN_PATTERN.fullmatch(normalized)
    if match is not None:
        _normalize_rating(match.group("previous"))
        action = (
            RatingAction.UPGRADED
            if match.group("verb").lower() == "повысило"
            else RatingAction.DOWNGRADED
        )
        return (
            _require_simple_subject(match.group("subject")),
            _normalize_rating(match.group("rating")),
            action,
            _normalize_outlook(match.group("tail")),
        )

    match = _WITHDRAW_PATTERN.fullmatch(normalized)
    if match is not None:
        subject = _require_simple_subject(match.group("subject"))
        subject_upper = f" {subject.upper()} "
        if " ПРОГНОЗ " in subject_upper:
            raise NcrRatingActionsSourceError(
                CreditRatingSourceErrorCode.SCHEMA_INVALID.value
            )
        return subject, None, RatingAction.WITHDRAWN, None

    if re.search(r" (?:на уровне|до) ", normalized, re.IGNORECASE):
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.RATING_INVALID.value
        )
    raise NcrRatingActionsSourceError(CreditRatingSourceErrorCode.SCHEMA_INVALID.value)


def parse_ncr_issuer_rating_actions_html(
    payload: bytes,
    *,
    retrieved_at: datetime | None = None,
) -> NcrIssuerRatingActionsSnapshotV1:
    checked_at = _aware_utc(retrieved_at)
    if not isinstance(payload, bytes) or not payload:
        raise NcrRatingActionsSourceError(CreditRatingSourceErrorCode.EMPTY.value)
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.HTML_INVALID.value
        ) from exc

    parser = _VisibleLinkParser()
    try:
        parser.feed(text)
        parser.close()
        if parser._anchor_open or parser._ignored_tags:
            raise NcrRatingActionsSourceError(
                CreditRatingSourceErrorCode.HTML_INVALID.value
            )
    except NcrRatingActionsSourceError:
        raise
    except (AssertionError, RecursionError, ValueError) as exc:
        raise NcrRatingActionsSourceError(
            CreditRatingSourceErrorCode.HTML_INVALID.value
        ) from exc

    events = _list_scope(tuple(parser.events))
    source = MarketSourceV1(
        provider=NCR_RATING_ACTIONS_PROVIDER,
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=checked_at,
        source_id=NCR_RATING_ACTIONS_SOURCE_ID,
    )
    records_by_url: dict[str, NcrIssuerRatingActionV1] = {}
    for index, event in enumerate(events):
        if event.href is None:
            continue
        parsed_title = _parse_action_title(event.text)
        if parsed_title is None:
            continue
        subject, rating, action, outlook = parsed_title
        release_match, release_url = _release_match(event.href)
        published_on = _find_publication_date(
            events,
            index=index,
            release_url=release_url,
            retrieved_at=checked_at,
        )
        release_date = date(
            2000 + int(release_match.group("year")),
            int(release_match.group("month")),
            int(release_match.group("day")),
        )
        if release_date != published_on:
            raise NcrRatingActionsSourceError(
                CreditRatingSourceErrorCode.IDENTITY_INVALID.value
            )
        try:
            record = NcrIssuerRatingActionV1(
                subject_name=subject,
                rating=rating,
                action=action,
                outlook=outlook,
                published_on=published_on,
                release_url=release_url,
                source=source,
            )
        except ValidationError as exc:
            raise NcrRatingActionsSourceError(
                CreditRatingSourceErrorCode.SCHEMA_INVALID.value
            ) from exc
        previous = records_by_url.get(release_url)
        if previous is not None and previous != record:
            raise NcrRatingActionsSourceError(
                CreditRatingSourceErrorCode.DUPLICATE_CONFLICT.value
            )
        records_by_url[release_url] = record
        if len(records_by_url) >= MAX_NCR_RECORDS:
            break

    records = tuple(
        sorted(
            records_by_url.values(),
            key=lambda item: (item.published_on, item.release_url),
            reverse=True,
        )
    )
    if not records:
        raise NcrRatingActionsSourceError(CreditRatingSourceErrorCode.EMPTY.value)
    return NcrIssuerRatingActionsSnapshotV1(
        retrieved_at=checked_at,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=source,
        records=records,
    )


def _unavailable(
    *,
    retrieved_at: datetime,
    error_code: CreditRatingSourceErrorCode,
) -> NcrIssuerRatingActionsSnapshotV1:
    return NcrIssuerRatingActionsSnapshotV1(
        retrieved_at=retrieved_at,
        status=CreditRatingSourceStatus.UNAVAILABLE,
        error_code=error_code,
    )


def _error_code_from_exception(
    error: NcrRatingActionsSourceError,
) -> CreditRatingSourceErrorCode:
    try:
        return CreditRatingSourceErrorCode(str(error))
    except ValueError:
        return CreditRatingSourceErrorCode.SCHEMA_INVALID


def _valid_fetch_controls(
    *,
    timeout_seconds: object,
    max_response_bytes: object,
) -> bool:
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or isinstance(max_response_bytes, bool)
        or not isinstance(max_response_bytes, int)
    ):
        return False
    try:
        timeout_value = float(timeout_seconds)
    except (OverflowError, ValueError):
        return False
    return (
        math.isfinite(timeout_value)
        and 0 < timeout_value <= DEFAULT_NCR_TIMEOUT_SECONDS
        and 1 <= max_response_bytes <= DEFAULT_NCR_MAX_RESPONSE_BYTES
    )


def _build_public_request(*, timeout_seconds: float) -> httpx.Request:
    return httpx.Request(
        "GET",
        NCR_RATING_ACTIONS_ENDPOINT,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "omni-cio-gateway/1.0",
        },
        extensions={"timeout": httpx.Timeout(timeout_seconds).as_dict()},
    )


def fetch_ncr_issuer_rating_actions(
    *,
    transport: httpx.BaseTransport | None = None,
    retrieved_at: datetime | None = None,
    timeout_seconds: float = DEFAULT_NCR_TIMEOUT_SECONDS,
    max_response_bytes: int = DEFAULT_NCR_MAX_RESPONSE_BYTES,
) -> NcrIssuerRatingActionsSnapshotV1:
    checked_at = _aware_utc(retrieved_at)
    if (
        transport is not None and not isinstance(transport, httpx.BaseTransport)
    ) or not _valid_fetch_controls(
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
    ):
        return _unavailable(
            retrieved_at=checked_at,
            error_code=CreditRatingSourceErrorCode.SCHEMA_INVALID,
        )

    active_client = httpx.Client(
        transport=transport,
        timeout=timeout_seconds,
        follow_redirects=False,
        trust_env=False,
    )
    request = _build_public_request(timeout_seconds=float(timeout_seconds))
    try:
        response = active_client.send(
            request,
            stream=True,
            auth=None,
            follow_redirects=False,
        )
        try:
            if str(response.url) != NCR_RATING_ACTIONS_ENDPOINT:
                return _unavailable(
                    retrieved_at=checked_at,
                    error_code=CreditRatingSourceErrorCode.URL_INVALID,
                )
            if response.status_code != 200:
                return _unavailable(
                    retrieved_at=checked_at,
                    error_code=CreditRatingSourceErrorCode.HTTP_ERROR,
                )
            content_type = response.headers.get("content-type", "")
            media_type = content_type.split(";", 1)[0].strip().lower()
            if media_type not in _ALLOWED_CONTENT_TYPES:
                return _unavailable(
                    retrieved_at=checked_at,
                    error_code=CreditRatingSourceErrorCode.CONTENT_TYPE_INVALID,
                )
            content_length = response.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    return _unavailable(
                        retrieved_at=checked_at,
                        error_code=CreditRatingSourceErrorCode.SCHEMA_INVALID,
                    )
                if declared_size < 0 or declared_size > max_response_bytes:
                    return _unavailable(
                        retrieved_at=checked_at,
                        error_code=CreditRatingSourceErrorCode.RESPONSE_TOO_LARGE,
                    )
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > max_response_bytes:
                    return _unavailable(
                        retrieved_at=checked_at,
                        error_code=CreditRatingSourceErrorCode.RESPONSE_TOO_LARGE,
                    )
                chunks.append(chunk)
            payload = b"".join(chunks)
        finally:
            response.close()
    except httpx.HTTPError:
        return _unavailable(
            retrieved_at=checked_at,
            error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
        )
    finally:
        active_client.close()

    try:
        return parse_ncr_issuer_rating_actions_html(
            payload,
            retrieved_at=checked_at,
        )
    except NcrRatingActionsSourceError as exc:
        return _unavailable(
            retrieved_at=checked_at,
            error_code=_error_code_from_exception(exc),
        )
