from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
import re
from typing import Final
from urllib.parse import urljoin, urlparse

import httpx
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


EXPERT_RA_RATING_ACTIONS_ENDPOINT: Final = "https://raexpert.ru/"
EXPERT_RA_RATING_ACTIONS_PROVIDER: Final = "Expert RA"
EXPERT_RA_RATING_ACTIONS_SOURCE_ID: Final = "EXPERT_RA.home.rating_actions"
DEFAULT_EXPERT_RA_TIMEOUT_SECONDS: Final = 10.0
DEFAULT_EXPERT_RA_MAX_RESPONSE_BYTES: Final = 1_500_000
MAX_EXPERT_RA_RECORDS: Final = 30

_ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
_ALLOWED_RELEASE_HOSTS = frozenset({"raexpert.ru", "www.raexpert.ru"})
_ALLOWED_RELEASE_PATH = re.compile(
    r"^/releases/(?P<year>20[0-9]{2})/"
    r"(?P<slug>[a-z]{3}(?:0[1-9]|[12][0-9]|3[01])[a-z]?)/?$",
    re.IGNORECASE,
)
_DATE_PATTERN = re.compile(
    r"^(?P<day>0[1-9]|[12][0-9]|3[01])\."
    r"(?P<month>0[1-9]|1[0-2])\."
    r"(?P<year>20[0-9]{2})$"
)
_RATING_TOKEN = r"ru(?:[AАBВCС]{1,3}|[RР][DД]|[DД])[+-]?"
_AGENCY_PREFIX = r"[«\"]?Эксперт РА[»\"]?"
_RATING_OBJECT = r"(?:кредитный рейтинг|рейтинг кредитоспособности)"
_ASSIGN_AFFIRM_PATTERN = re.compile(
    rf"^{_AGENCY_PREFIX} (?P<verb>присвоил|подтвердил) {_RATING_OBJECT} "
    rf"(?P<subject>.+?) на уровне (?P<rating>{_RATING_TOKEN})(?P<tail>.*)$",
    re.IGNORECASE,
)
_UP_DOWN_PATTERN = re.compile(
    rf"^{_AGENCY_PREFIX} (?P<verb>повысил|понизил) {_RATING_OBJECT} "
    rf"(?P<subject>.+?) до уровня (?P<rating>{_RATING_TOKEN})(?P<tail>.*)$",
    re.IGNORECASE,
)
_WITHDRAW_PATTERN = re.compile(
    rf"^{_AGENCY_PREFIX} отозвал(?: без подтверждения)? {_RATING_OBJECT} "
    r"(?P<subject>.+?)(?: в связи с .+)?$",
    re.IGNORECASE,
)
_OUTLOOK_TAIL = re.compile(
    r"^(?:"
    r"(?:, |и )изменил прогноз(?: по рейтингу)? на "
    r"(?P<changed>стабильный|позитивный|негативный|развивающийся)"
    r"(?: и (?:продлил|установил|снял) статус [«\"]под наблюдением[»\"])?"
    r"|со (?P<with>стабильным|позитивным|негативным|развивающимся) прогнозом"
    r")?$",
    re.IGNORECASE,
)
_ACTION_WORDS = ("ПРИСВОИЛ", "ПОДТВЕРДИЛ", "ПОВЫСИЛ", "ПОНИЗИЛ", "ОТОЗВАЛ")
_UNSUPPORTED_COMPLEX = (
    "ПЕРЕСМОТРЕЛ И ПРИСВОИЛ",
    "ОЖИДАЕМЫЙ КРЕДИТНЫЙ РЕЙТИНГ",
    "КРЕДИТНЫЕ РЕЙТИНГИ",
    "РЕЙТИНГИ КРЕДИТОСПОСОБНОСТИ",
)
_ISSUE_MARKERS = (
    " ОБЛИГАЦ",
    " ВЫПУСК",
    " СЕРИИ ",
    " СЕРИЯ ",
    " ТРАНШ",
    " КЛАСС ",
    " STRUCTUR",
    " ISIN",
    " ДОЛГОВОГО ИНСТРУМЕНТА",
    " ИНСТРУМЕНТА СТРУКТУРИРОВАННОГО ФИНАНСИРОВАНИЯ",
)
_CONFUSABLES = str.maketrans(
    {
        "А": "A",
        "а": "A",
        "В": "B",
        "в": "B",
        "С": "C",
        "с": "C",
        "Р": "R",
        "р": "R",
        "Д": "D",
        "д": "D",
    }
)
_SUPPORTED_RATINGS = frozenset(
    {
        "ruAAA",
        "ruAA+",
        "ruAA",
        "ruAA-",
        "ruA+",
        "ruA",
        "ruA-",
        "ruBBB+",
        "ruBBB",
        "ruBBB-",
        "ruBB+",
        "ruBB",
        "ruBB-",
        "ruB+",
        "ruB",
        "ruB-",
        "ruCCC",
        "ruCC",
        "ruC",
        "ruRD",
        "ruD",
    }
)
_SENSITIVE_REQUEST_HEADERS = (
    "authorization",
    "proxy-authorization",
    "cookie",
)
_MAX_CLOCK_SKEW = timedelta(days=1)


class ExpertRaRatingActionsSourceError(ValueError):
    """The fixed official Expert RA action source cannot be handled safely."""


@dataclass(frozen=True)
class _HtmlEvent:
    text: str
    href: str | None


class _VisibleLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.events: list[_HtmlEvent] = []
        self._href: str | None = None
        self._anchor_chunks: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            self._ignored_depth += 1
            return
        if lowered == "a" and self._ignored_depth == 0:
            if self._href is not None:
                raise ExpertRaRatingActionsSourceError(
                    CreditRatingSourceErrorCode.HTML_INVALID.value
                )
            self._href = next(
                (value for name, value in attrs if name.lower() == "href"),
                None,
            )
            self._anchor_chunks = []

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)
            return
        if lowered == "a" and self._href is not None:
            text = _normalize_text(" ".join(self._anchor_chunks))
            if text:
                self.events.append(_HtmlEvent(text=text, href=self._href))
            self._href = None
            self._anchor_chunks = []

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        text = _normalize_text(data)
        if not text:
            return
        if self._href is not None:
            self._anchor_chunks.append(text)
        else:
            self.events.append(_HtmlEvent(text=text, href=None))

    def error(self, message: str) -> None:
        raise ExpertRaRatingActionsSourceError(message)


def _normalize_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
        )
    return result.astimezone(timezone.utc)


def _canonical_release_url(href: str) -> str:
    if not isinstance(href, str) or not href.strip():
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.URL_INVALID.value
        )
    joined = urljoin(EXPERT_RA_RATING_ACTIONS_ENDPOINT, href.strip())
    parsed = urlparse(joined)
    if (
        parsed.scheme != "https"
        or parsed.netloc.lower() not in _ALLOWED_RELEASE_HOSTS
        or parsed.query
        or parsed.fragment
    ):
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.URL_INVALID.value
        )
    match = _ALLOWED_RELEASE_PATH.fullmatch(parsed.path)
    if match is None:
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.URL_INVALID.value
        )
    return (
        "https://raexpert.ru/releases/"
        f"{match.group('year')}/{match.group('slug').lower()}"
    )


def _parse_date(text: str, *, retrieved_at: datetime) -> date:
    match = _DATE_PATTERN.fullmatch(text)
    if match is None:
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
        )
    try:
        parsed = date(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError as exc:
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
        ) from exc
    if parsed > (retrieved_at + _MAX_CLOCK_SKEW).date():
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
        )
    return parsed


def _rating_action_scope(
    events: tuple[_HtmlEvent, ...],
) -> tuple[_HtmlEvent, ...]:
    start = next(
        (
            index
            for index, event in enumerate(events)
            if event.href is None and event.text == "Рейтинговые действия"
        ),
        None,
    )
    if start is None:
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.SCHEMA_INVALID.value
        )
    end = next(
        (
            index
            for index, event in enumerate(events[start + 1 :], start + 1)
            if event.href is None and event.text == "Аналитика"
        ),
        None,
    )
    if end is None or end <= start + 1:
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.SCHEMA_INVALID.value
        )
    return events[start + 1 : end]


def _find_publication_date(
    events: tuple[_HtmlEvent, ...],
    *,
    index: int,
    retrieved_at: datetime,
) -> date:
    for candidate in events[index + 1 : min(len(events), index + 8)]:
        if _DATE_PATTERN.fullmatch(candidate.text):
            return _parse_date(candidate.text, retrieved_at=retrieved_at)
        if _is_action_title(candidate.text):
            break
    raise ExpertRaRatingActionsSourceError(
        CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
    )


def _normalize_rating(value: str) -> str:
    translated = _normalize_text(value).translate(_CONFUSABLES)
    if not translated.lower().startswith("ru"):
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.RATING_INVALID.value
        )
    result = f"ru{translated[2:].upper()}"
    if result not in _SUPPORTED_RATINGS:
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.RATING_INVALID.value
        )
    return result


def _normalize_outlook(tail: str) -> CreditRatingOutlook | None:
    normalized = _normalize_text(tail)
    match = _OUTLOOK_TAIL.fullmatch(normalized)
    if match is None:
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.OUTLOOK_INVALID.value
        )
    value = match.group("changed") or match.group("with")
    if value is None:
        return None
    root = value.lower()
    if root.startswith("стабиль"):
        return CreditRatingOutlook.STABLE
    if root.startswith("позитив"):
        return CreditRatingOutlook.POSITIVE
    if root.startswith("негатив"):
        return CreditRatingOutlook.NEGATIVE
    if root.startswith("развива"):
        return CreditRatingOutlook.DEVELOPING
    raise ExpertRaRatingActionsSourceError(
        CreditRatingSourceErrorCode.OUTLOOK_INVALID.value
    )


def _require_simple_subject(value: str) -> str:
    result = _normalize_text(value.strip(" ,.;"))
    upper = f" {result.upper()} "
    if (
        not result
        or len(result) > 256
        or any(marker in upper for marker in _ISSUE_MARKERS)
        or re.search(_RATING_TOKEN, result, re.IGNORECASE)
    ):
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.IDENTITY_INVALID.value
        )
    return result


def _is_action_title(value: str) -> bool:
    upper = _normalize_text(value).upper()
    return "ЭКСПЕРТ РА" in upper and any(word in upper for word in _ACTION_WORDS)


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
    if "КРЕДИТНЫЙ РЕЙТИНГ" not in normalized.upper() and (
        "РЕЙТИНГ КРЕДИТОСПОСОБНОСТИ" not in normalized.upper()
    ):
        return None

    match = _ASSIGN_AFFIRM_PATTERN.fullmatch(normalized)
    if match is not None:
        action = (
            RatingAction.ASSIGNED
            if match.group("verb").lower() == "присвоил"
            else RatingAction.AFFIRMED
        )
        return (
            _require_simple_subject(match.group("subject")),
            _normalize_rating(match.group("rating")),
            action,
            _normalize_outlook(match.group("tail")),
        )

    match = _UP_DOWN_PATTERN.fullmatch(normalized)
    if match is not None:
        action = (
            RatingAction.UPGRADED
            if match.group("verb").lower() == "повысил"
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
        return (
            _require_simple_subject(match.group("subject")),
            None,
            RatingAction.WITHDRAWN,
            None,
        )

    if re.search(r" (?:на|до) уровне (?!ru)", normalized, re.IGNORECASE):
        return None
    raise ExpertRaRatingActionsSourceError(
        CreditRatingSourceErrorCode.SCHEMA_INVALID.value
    )


def parse_expert_ra_issuer_rating_actions_html(
    payload: bytes,
    *,
    retrieved_at: datetime | None = None,
) -> ExpertRaIssuerRatingActionsSnapshotV1:
    checked_at = _aware_utc(retrieved_at)
    if not isinstance(payload, bytes) or not payload:
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.EMPTY.value
        )
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.HTML_INVALID.value
        ) from exc

    parser = _VisibleLinkParser()
    try:
        parser.feed(text)
        parser.close()
    except ExpertRaRatingActionsSourceError:
        raise
    except (AssertionError, RecursionError, ValueError) as exc:
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.HTML_INVALID.value
        ) from exc

    events = _rating_action_scope(tuple(parser.events))
    source = MarketSourceV1(
        provider=EXPERT_RA_RATING_ACTIONS_PROVIDER,
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=checked_at,
        source_id=EXPERT_RA_RATING_ACTIONS_SOURCE_ID,
    )
    records_by_url: dict[str, ExpertRaIssuerRatingActionV1] = {}
    for index, event in enumerate(events):
        if event.href is None:
            continue
        parsed_title = _parse_action_title(event.text)
        if parsed_title is None:
            continue
        subject, rating, action, outlook = parsed_title
        release_url = _canonical_release_url(event.href)
        published_on = _find_publication_date(
            events,
            index=index,
            retrieved_at=checked_at,
        )
        try:
            record = ExpertRaIssuerRatingActionV1(
                subject_name=subject,
                rating=rating,
                action=action,
                outlook=outlook,
                published_on=published_on,
                release_url=release_url,
                source=source,
            )
        except ValidationError as exc:
            raise ExpertRaRatingActionsSourceError(
                CreditRatingSourceErrorCode.SCHEMA_INVALID.value
            ) from exc
        previous = records_by_url.get(release_url)
        if previous is not None and previous != record:
            raise ExpertRaRatingActionsSourceError(
                CreditRatingSourceErrorCode.DUPLICATE_CONFLICT.value
            )
        records_by_url[release_url] = record
        if len(records_by_url) > MAX_EXPERT_RA_RECORDS:
            raise ExpertRaRatingActionsSourceError(
                CreditRatingSourceErrorCode.RESPONSE_TOO_LARGE.value
            )

    records = tuple(
        sorted(
            records_by_url.values(),
            key=lambda item: (item.published_on, item.release_url),
            reverse=True,
        )
    )
    if not records:
        raise ExpertRaRatingActionsSourceError(
            CreditRatingSourceErrorCode.EMPTY.value
        )
    return ExpertRaIssuerRatingActionsSnapshotV1(
        retrieved_at=checked_at,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=source,
        records=records,
    )


def _unavailable(
    *,
    retrieved_at: datetime,
    error_code: CreditRatingSourceErrorCode,
) -> ExpertRaIssuerRatingActionsSnapshotV1:
    return ExpertRaIssuerRatingActionsSnapshotV1(
        retrieved_at=retrieved_at,
        status=CreditRatingSourceStatus.UNAVAILABLE,
        error_code=error_code,
    )


def _error_code_from_exception(
    error: ExpertRaRatingActionsSourceError,
) -> CreditRatingSourceErrorCode:
    try:
        return CreditRatingSourceErrorCode(str(error))
    except ValueError:
        return CreditRatingSourceErrorCode.SCHEMA_INVALID


def _build_public_request(client: httpx.Client) -> httpx.Request:
    request = client.build_request(
        "GET",
        EXPERT_RA_RATING_ACTIONS_ENDPOINT,
        headers={"Accept": "text/html,application/xhtml+xml"},
    )
    for header in _SENSITIVE_REQUEST_HEADERS:
        if header in request.headers:
            del request.headers[header]
    return request


def fetch_expert_ra_issuer_rating_actions(
    *,
    client: httpx.Client | None = None,
    retrieved_at: datetime | None = None,
    timeout_seconds: float = DEFAULT_EXPERT_RA_TIMEOUT_SECONDS,
    max_response_bytes: int = DEFAULT_EXPERT_RA_MAX_RESPONSE_BYTES,
) -> ExpertRaIssuerRatingActionsSnapshotV1:
    checked_at = _aware_utc(retrieved_at)
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or timeout_seconds <= 0
        or isinstance(max_response_bytes, bool)
        or not isinstance(max_response_bytes, int)
        or max_response_bytes < 1
    ):
        return _unavailable(
            retrieved_at=checked_at,
            error_code=CreditRatingSourceErrorCode.SCHEMA_INVALID,
        )

    owned_client = client is None
    active_client = client or httpx.Client(
        timeout=timeout_seconds,
        follow_redirects=False,
        trust_env=False,
        headers={"Accept": "text/html,application/xhtml+xml"},
    )
    request = _build_public_request(active_client)
    try:
        response = active_client.send(
            request,
            stream=True,
            follow_redirects=False,
        )
        try:
            if str(response.url) != EXPERT_RA_RATING_ACTIONS_ENDPOINT:
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
        if owned_client:
            active_client.close()

    try:
        return parse_expert_ra_issuer_rating_actions_html(
            payload,
            retrieved_at=checked_at,
        )
    except ExpertRaRatingActionsSourceError as exc:
        return _unavailable(
            retrieved_at=checked_at,
            error_code=_error_code_from_exception(exc),
        )
