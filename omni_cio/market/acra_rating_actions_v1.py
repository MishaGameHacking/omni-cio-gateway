from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
import re
from typing import Final
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import ValidationError

from omni_cio.contracts.v1.market import MarketSourceV1, RatingAction, SourceAuthority
from omni_cio.contracts.v1.ratings import (
    AcraIssuerRatingActionsSnapshotV1,
    AcraIssuerRatingActionV1,
    CreditRatingOutlook,
    CreditRatingSourceErrorCode,
    CreditRatingSourceStatus,
)


ACRA_RATING_ACTIONS_ENDPOINT: Final = (
    "https://www.acra-ratings.ru/press-releases/?count=30&lang=en"
)
ACRA_RATING_ACTIONS_PROVIDER: Final = "ACRA"
ACRA_RATING_ACTIONS_SOURCE_ID: Final = "ACRA.press_releases.issuer_rating_actions"
DEFAULT_ACRA_TIMEOUT_SECONDS: Final = 10.0
DEFAULT_ACRA_MAX_RESPONSE_BYTES: Final = 1_000_000
MAX_ACRA_RECORDS: Final = 30

_ALLOWED_CONTENT_TYPES = {"text/html", "application/xhtml+xml"}
_ALLOWED_RELEASE_HOST = "www.acra-ratings.ru"
_ALLOWED_RELEASE_PATH = re.compile(r"^/press-releases/(?P<id>[1-9][0-9]*)/?$")
_DATE_PATTERN = re.compile(
    r"^(?P<day>[1-9]|[12][0-9]|3[01]) "
    r"(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
    r"(?P<year>20[0-9]{2})$"
)
_RATING = r"(?:e)?(?:AAA|AA|A|BBB|BB|B|CCC|CC|C|D)[+-]?\(RU\)"
_OUTLOOK = r"STABLE|POSITIVE|NEGATIVE|DEVELOPING|UNDER REVISION"
_ASSIGN_AFFIRM_PATTERN = re.compile(
    rf"^ACRA (?P<verb>ASSIGNS|AFFIRMS) (?P<rating>{_RATING}) TO "
    rf"(?P<subject>.+?)(?:, (?:(?:CHANGES )?OUTLOOK TO |OUTLOOK )"
    rf"(?P<outlook>{_OUTLOOK}))?$",
    re.IGNORECASE,
)
_UP_DOWN_PATTERN = re.compile(
    rf"^ACRA (?P<verb>UPGRADES|DOWNGRADES) (?P<subject>.+?) TO "
    rf"(?P<rating>{_RATING})(?:, (?:(?:CHANGES )?OUTLOOK TO |OUTLOOK )"
    rf"(?P<outlook>{_OUTLOOK}))?$",
    re.IGNORECASE,
)
_WITHDRAW_PATTERN = re.compile(
    r"^ACRA WITHDRAWS THE CREDIT RATING OF (?P<subject>.+?)"
    r"(?: IN VIEW OF .+)?$",
    re.IGNORECASE,
)
_ACTION_WORDS = ("ASSIGNS", "AFFIRMS", "UPGRADES", "DOWNGRADES", "WITHDRAWS")
_ISSUE_MARKERS = (
    " BOND ",
    " BONDS ",
    " BOND ISSUE",
    " NOTES ",
    " NOTE ISSUE",
    " TRANCHE ",
    " RMBS ",
    " SERIES ",
    " CLASS ",
    " SECURITIES ",
)
_MAX_CLOCK_SKEW = timedelta(days=1)


class AcraRatingActionsSourceError(ValueError):
    """The official ACRA rating-action source cannot be handled safely."""


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
                raise AcraRatingActionsSourceError(
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
        raise AcraRatingActionsSourceError(message)


def _normalize_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise AcraRatingActionsSourceError(
            CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
        )
    return result.astimezone(timezone.utc)


def _canonical_release_url(href: str) -> str:
    if not isinstance(href, str) or not href.strip():
        raise AcraRatingActionsSourceError(
            CreditRatingSourceErrorCode.URL_INVALID.value
        )
    joined = urljoin("https://www.acra-ratings.ru", href.strip())
    parsed = urlparse(joined)
    if (
        parsed.scheme != "https"
        or parsed.netloc != _ALLOWED_RELEASE_HOST
        or parsed.query not in {"", "lang=en"}
        or parsed.fragment
    ):
        raise AcraRatingActionsSourceError(
            CreditRatingSourceErrorCode.URL_INVALID.value
        )
    match = _ALLOWED_RELEASE_PATH.fullmatch(parsed.path)
    if match is None:
        raise AcraRatingActionsSourceError(
            CreditRatingSourceErrorCode.URL_INVALID.value
        )
    return (
        "https://www.acra-ratings.ru/press-releases/"
        f"{match.group('id')}/?lang=en"
    )


def _parse_date(text: str, *, retrieved_at: datetime) -> date:
    match = _DATE_PATTERN.fullmatch(text)
    if match is None:
        raise AcraRatingActionsSourceError(
            CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
        )
    try:
        parsed = datetime.strptime(text, "%d %b %Y").date()
    except ValueError as exc:
        raise AcraRatingActionsSourceError(
            CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
        ) from exc
    if parsed > (retrieved_at + _MAX_CLOCK_SKEW).date():
        raise AcraRatingActionsSourceError(
            CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
        )
    return parsed


def _find_publication_date(
    events: tuple[_HtmlEvent, ...],
    *,
    index: int,
    retrieved_at: datetime,
) -> date:
    upper = min(len(events), index + 12)
    for candidate in events[index + 1 : upper]:
        if candidate.href is not None and candidate.text.upper().startswith("ACRA "):
            break
        if _DATE_PATTERN.fullmatch(candidate.text):
            return _parse_date(candidate.text, retrieved_at=retrieved_at)
    raise AcraRatingActionsSourceError(
        CreditRatingSourceErrorCode.TIMESTAMP_INVALID.value
    )


def _normalize_outlook(value: str | None) -> CreditRatingOutlook | None:
    if value is None:
        return None
    mapping = {
        "STABLE": CreditRatingOutlook.STABLE,
        "POSITIVE": CreditRatingOutlook.POSITIVE,
        "NEGATIVE": CreditRatingOutlook.NEGATIVE,
        "DEVELOPING": CreditRatingOutlook.DEVELOPING,
        "UNDER REVISION": CreditRatingOutlook.UNDER_REVISION,
    }
    try:
        return mapping[value.upper()]
    except KeyError as exc:
        raise AcraRatingActionsSourceError(
            CreditRatingSourceErrorCode.OUTLOOK_INVALID.value
        ) from exc


def _require_simple_subject(value: str) -> str:
    result = _normalize_text(value.strip(" ,.;"))
    if (
        not result
        or len(result) > 256
        or " AND " in result.upper()
        or re.search(_RATING, result, re.IGNORECASE)
    ):
        raise AcraRatingActionsSourceError(
            CreditRatingSourceErrorCode.IDENTITY_INVALID.value
        )
    return result


def _is_issue_level_title(title: str) -> bool:
    padded = f" {title.upper()} "
    return any(marker in padded for marker in _ISSUE_MARKERS)


def _normalized_rating(value: str) -> str:
    result = value.upper()
    return result.replace("E", "e", 1) if result.startswith("E") else result


def _parse_action_title(
    title: str,
) -> tuple[str, str | None, RatingAction, CreditRatingOutlook | None] | None:
    normalized = _normalize_text(title)
    upper = normalized.upper()
    if not upper.startswith("ACRA "):
        return None
    if not any(word in upper for word in _ACTION_WORDS):
        return None
    if _is_issue_level_title(upper):
        return None

    rating_matches = re.findall(_RATING, normalized, flags=re.IGNORECASE)
    if " AND " in upper or len(rating_matches) > 1:
        return None
    if "WITHDRAWS" not in upper and not rating_matches:
        return None

    match = _ASSIGN_AFFIRM_PATTERN.fullmatch(normalized)
    if match is not None:
        action = (
            RatingAction.ASSIGNED
            if match.group("verb").upper() == "ASSIGNS"
            else RatingAction.AFFIRMED
        )
        return (
            _require_simple_subject(match.group("subject")),
            _normalized_rating(match.group("rating")),
            action,
            _normalize_outlook(match.group("outlook")),
        )

    match = _UP_DOWN_PATTERN.fullmatch(normalized)
    if match is not None:
        action = (
            RatingAction.UPGRADED
            if match.group("verb").upper() == "UPGRADES"
            else RatingAction.DOWNGRADED
        )
        return (
            _require_simple_subject(match.group("subject")),
            _normalized_rating(match.group("rating")),
            action,
            _normalize_outlook(match.group("outlook")),
        )

    match = _WITHDRAW_PATTERN.fullmatch(normalized)
    if match is not None:
        return (
            _require_simple_subject(match.group("subject")),
            None,
            RatingAction.WITHDRAWN,
            None,
        )

    raise AcraRatingActionsSourceError(
        CreditRatingSourceErrorCode.SCHEMA_INVALID.value
    )


def parse_acra_issuer_rating_actions_html(
    payload: bytes,
    *,
    retrieved_at: datetime | None = None,
) -> AcraIssuerRatingActionsSnapshotV1:
    checked_at = _aware_utc(retrieved_at)
    if not isinstance(payload, bytes) or not payload:
        raise AcraRatingActionsSourceError(
            CreditRatingSourceErrorCode.EMPTY.value
        )
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AcraRatingActionsSourceError(
            CreditRatingSourceErrorCode.HTML_INVALID.value
        ) from exc

    parser = _VisibleLinkParser()
    try:
        parser.feed(text)
        parser.close()
    except AcraRatingActionsSourceError:
        raise
    except (AssertionError, RecursionError, ValueError) as exc:
        raise AcraRatingActionsSourceError(
            CreditRatingSourceErrorCode.HTML_INVALID.value
        ) from exc

    source = MarketSourceV1(
        provider=ACRA_RATING_ACTIONS_PROVIDER,
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=checked_at,
        source_id=ACRA_RATING_ACTIONS_SOURCE_ID,
    )
    events = tuple(parser.events)
    records_by_url: dict[str, AcraIssuerRatingActionV1] = {}

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
            record = AcraIssuerRatingActionV1(
                subject_name=subject,
                rating=rating,
                action=action,
                outlook=outlook,
                published_on=published_on,
                release_url=release_url,
                source=source,
            )
        except ValidationError as exc:
            raise AcraRatingActionsSourceError(
                CreditRatingSourceErrorCode.SCHEMA_INVALID.value
            ) from exc

        previous = records_by_url.get(release_url)
        if previous is not None and previous != record:
            raise AcraRatingActionsSourceError(
                CreditRatingSourceErrorCode.DUPLICATE_CONFLICT.value
            )
        records_by_url[release_url] = record
        if len(records_by_url) > MAX_ACRA_RECORDS:
            raise AcraRatingActionsSourceError(
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
        raise AcraRatingActionsSourceError(
            CreditRatingSourceErrorCode.EMPTY.value
        )
    return AcraIssuerRatingActionsSnapshotV1(
        retrieved_at=checked_at,
        status=CreditRatingSourceStatus.AVAILABLE,
        source=source,
        records=records,
    )


def _error_code_from_exception(
    error: AcraRatingActionsSourceError,
) -> CreditRatingSourceErrorCode:
    try:
        return CreditRatingSourceErrorCode(str(error))
    except ValueError:
        return CreditRatingSourceErrorCode.SCHEMA_INVALID


def _unavailable(
    *,
    retrieved_at: datetime,
    error_code: CreditRatingSourceErrorCode,
) -> AcraIssuerRatingActionsSnapshotV1:
    return AcraIssuerRatingActionsSnapshotV1(
        retrieved_at=retrieved_at,
        status=CreditRatingSourceStatus.UNAVAILABLE,
        error_code=error_code,
    )


def fetch_acra_issuer_rating_actions(
    *,
    client: httpx.Client | None = None,
    retrieved_at: datetime | None = None,
    timeout_seconds: float = DEFAULT_ACRA_TIMEOUT_SECONDS,
    max_response_bytes: int = DEFAULT_ACRA_MAX_RESPONSE_BYTES,
) -> AcraIssuerRatingActionsSnapshotV1:
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
    try:
        with active_client.stream(
            "GET",
            ACRA_RATING_ACTIONS_ENDPOINT,
            headers={"Accept": "text/html,application/xhtml+xml"},
        ) as response:
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
    except httpx.HTTPError:
        return _unavailable(
            retrieved_at=checked_at,
            error_code=CreditRatingSourceErrorCode.NETWORK_ERROR,
        )
    finally:
        if owned_client:
            active_client.close()

    try:
        return parse_acra_issuer_rating_actions_html(
            payload,
            retrieved_at=checked_at,
        )
    except AcraRatingActionsSourceError as exc:
        return _unavailable(
            retrieved_at=checked_at,
            error_code=_error_code_from_exception(exc),
        )
