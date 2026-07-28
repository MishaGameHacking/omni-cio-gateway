from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable
from html.parser import HTMLParser

from omni_cio.contracts.v1.market import SourceAuthority
from omni_cio.contracts.v1.news import (
    DuplicateNewsOccurrenceV1,
    EntityResolutionStatus,
    InjectionFlag,
    NewsContentFormat,
    NewsContentKind,
    NewsDeduplicationResultV1,
    NewsDisposition,
    NewsDocumentInputV1,
    SanitizedNewsDocumentV1,
)


MAX_PARSE_INPUT_CHARS = 200_000
MAX_SANITIZED_TEXT_CHARS = 50_000

_BLOCKED_TAGS = {
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "form",
    "input",
    "button",
    "textarea",
    "select",
    "option",
    "template",
    "svg",
    "math",
    "canvas",
    "noscript",
}
_VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
_BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "div",
    "dl",
    "fieldset",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "li",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "td",
    "th",
    "tr",
    "ul",
}
_HIDDEN_CLASS_TOKENS = {"hidden", "d-none", "visually-hidden"}
_SUSPICIOUS_CODEPOINTS = {
    "\u061c",
    "\u200b",
    "\u200c",
    "\u200d",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2060",
    "\u2061",
    "\u2062",
    "\u2063",
    "\u2064",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
    "\ufeff",
}

_INJECTION_PATTERNS: tuple[tuple[InjectionFlag, tuple[str, ...]], ...] = (
    (
        InjectionFlag.SYSTEM_OVERRIDE,
        (
            r"\bignore\s+(all\s+)?previous\s+instructions?\b",
            r"\bdisregard\s+(the\s+)?system\s+prompt\b",
            r"\bnew\s+system\s+instructions?\b",
            r"\bигнорируй\s+(все\s+)?предыдущие\s+инструкции\b",
            r"\bзабудь\s+(все\s+)?предыдущие\s+инструкции\b",
            r"\bновые\s+системные\s+инструкции\b",
        ),
    ),
    (
        InjectionFlag.TOOL_CALL,
        (
            r"\b(call|invoke|execute)\s+(the\s+)?(tool|function|api|action)\b",
            r"\bвызови\s+(инструмент|функцию|api|action)\b",
            r"\bзапусти\s+(action|api|инструмент)\b",
        ),
    ),
    (
        InjectionFlag.CREDENTIAL_REQUEST,
        (
            r"\b(reveal|show|print|return)\s+(the\s+)?(api\s+key|token|password|secret)\b",
            r"\b(покажи|раскрой|выведи)\s+(api[- ]?ключ|токен|пароль|секрет)\b",
        ),
    ),
    (
        InjectionFlag.CODE_EXECUTION,
        (
            r"\b(execute|run)\s+(this\s+)?(code|shell|command|script)\b",
            r"\b(выполни|запусти)\s+(этот\s+)?(код|shell|команду|скрипт)\b",
        ),
    ),
    (
        InjectionFlag.TRADING_INSTRUCTION,
        (
            r"\b(place|submit|create|execute)\s+(a\s+)?(trade|order)\b",
            r"\b(создай|отправь|исполни)\s+(торговую\s+)?заявку\b",
            r"\bсоверши\s+сделку\b",
        ),
    ),
    (
        InjectionFlag.TRANSFER_OR_WITHDRAWAL,
        (
            r"\b(withdraw|transfer)\s+(the\s+)?(money|funds|cash|securities)\b",
            r"\b(выведи|переведи)\s+(деньги|средства|ценные\s+бумаги)\b",
        ),
    ),
)

_SEVERE_FLAGS = {
    InjectionFlag.SYSTEM_OVERRIDE,
    InjectionFlag.TOOL_CALL,
    InjectionFlag.CREDENTIAL_REQUEST,
    InjectionFlag.CODE_EXECUTION,
    InjectionFlag.TRADING_INSTRUCTION,
    InjectionFlag.TRANSFER_OR_WITHDRAWAL,
    InjectionFlag.EMPTY_AFTER_SANITIZATION,
}
_TRUSTED_AUTHORITIES = {
    SourceAuthority.PRIMARY,
    SourceAuthority.OFFICIAL,
    SourceAuthority.REGULATED,
}


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[tuple[str, bool]] = []
        self.suppressed_depth = 0
        self.hidden_content_found = False

    @staticmethod
    def _hidden_by_attributes(attrs: list[tuple[str, str | None]]) -> bool:
        values = {name.lower(): (value or "") for name, value in attrs}
        if "hidden" in values:
            return True
        if values.get("aria-hidden", "").strip().lower() == "true":
            return True
        style = re.sub(r"\s+", "", values.get("style", "").lower())
        if any(
            marker in style
            for marker in ("display:none", "visibility:hidden", "opacity:0")
        ):
            return True
        classes = set(values.get("class", "").lower().split())
        return bool(classes & _HIDDEN_CLASS_TOKENS)

    def _separator(self) -> None:
        if self.parts and self.parts[-1] != " ":
            self.parts.append(" ")

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        normalized_tag = tag.lower()
        explicitly_hidden = (
            normalized_tag in _BLOCKED_TAGS
            or self._hidden_by_attributes(attrs)
        )
        suppressed = self.suppressed_depth > 0 or explicitly_hidden
        if explicitly_hidden:
            self.hidden_content_found = True
        if normalized_tag in _BLOCK_TAGS and not suppressed:
            self._separator()
        if normalized_tag not in _VOID_TAGS:
            self.stack.append((normalized_tag, suppressed))
            if suppressed:
                self.suppressed_depth += 1

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        matching_index: int | None = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == normalized_tag:
                matching_index = index
                break
        if matching_index is None:
            return
        popped = self.stack[matching_index:]
        del self.stack[matching_index:]
        self.suppressed_depth -= sum(
            int(suppressed) for _, suppressed in popped
        )
        self.suppressed_depth = max(self.suppressed_depth, 0)
        if normalized_tag in _BLOCK_TAGS and self.suppressed_depth == 0:
            self._separator()

    def handle_data(self, data: str) -> None:
        if self.suppressed_depth == 0:
            self.parts.append(data)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _contains_suspicious_unicode(value: str) -> bool:
    return any(character in _SUSPICIOUS_CODEPOINTS for character in value)


def _normalize_visible_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    cleaned = "".join(
        character
        for character in normalized
        if character not in _SUSPICIOUS_CODEPOINTS
        and (
            character in "\n\r\t"
            or unicodedata.category(character) not in {"Cc", "Cf"}
        )
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def _sanitize_html(value: str) -> tuple[str, bool]:
    parser = _VisibleTextParser()
    parser.feed(value)
    parser.close()
    return (
        _normalize_visible_text("".join(parser.parts)),
        parser.hidden_content_found,
    )


def _detect_injection_flags(value: str) -> list[InjectionFlag]:
    lowered = _normalize_visible_text(value).casefold()
    flags: list[InjectionFlag] = []
    for flag, patterns in _INJECTION_PATTERNS:
        if any(
            re.search(pattern, lowered, flags=re.IGNORECASE)
            for pattern in patterns
        ):
            flags.append(flag)
    return flags


def _append_flag(flags: list[InjectionFlag], flag: InjectionFlag) -> None:
    if flag not in flags:
        flags.append(flag)


def _disposition(
    *,
    document: NewsDocumentInputV1,
    flags: tuple[InjectionFlag, ...],
) -> NewsDisposition:
    if any(flag in _SEVERE_FLAGS for flag in flags):
        return NewsDisposition.REJECTED
    if flags:
        return NewsDisposition.CONTEXT_ONLY
    if document.authority not in _TRUSTED_AUTHORITIES:
        return NewsDisposition.CONTEXT_ONLY
    if document.entity_resolution != EntityResolutionStatus.RESOLVED:
        return NewsDisposition.CONTEXT_ONLY
    if document.content_kind != NewsContentKind.FACT:
        return NewsDisposition.CONTEXT_ONLY
    return NewsDisposition.ACCEPTED


def sanitize_news_document(
    document: NewsDocumentInputV1,
) -> SanitizedNewsDocumentV1:
    """Sanitize one provided document without fetching or executing content."""
    truncated = len(document.raw_content) > MAX_PARSE_INPUT_CHARS
    bounded_raw = document.raw_content[:MAX_PARSE_INPUT_CHARS]
    suspicious_unicode = _contains_suspicious_unicode(
        f"{document.title}\n{bounded_raw}"
    )

    if document.content_format == NewsContentFormat.HTML:
        sanitized_text, hidden_content = _sanitize_html(bounded_raw)
    else:
        sanitized_text = _normalize_visible_text(bounded_raw)
        hidden_content = False
    sanitized_text = sanitized_text[:MAX_SANITIZED_TEXT_CHARS]
    normalized_title = _normalize_visible_text(document.title)[:512]
    if not normalized_title:
        normalized_title = "Untitled external document"

    flags = _detect_injection_flags(
        f"{normalized_title}\n{bounded_raw}\n{sanitized_text}"
    )
    if hidden_content:
        _append_flag(flags, InjectionFlag.HIDDEN_CONTENT)
    if suspicious_unicode:
        _append_flag(flags, InjectionFlag.SUSPICIOUS_UNICODE)
    if truncated:
        _append_flag(flags, InjectionFlag.OVERSIZED_CONTENT)
    if not sanitized_text:
        _append_flag(flags, InjectionFlag.EMPTY_AFTER_SANITIZATION)
    flags_tuple = tuple(flags)

    content_fingerprint = _sha256(
        f"{normalized_title.casefold()}\n{sanitized_text.casefold()}"
    )
    cluster_time = document.event_at or document.published_at
    cluster_key = (
        document.instrument_key
        if document.entity_resolution == EntityResolutionStatus.RESOLVED
        else document.entity_resolution.value
    )
    event_cluster_id = _sha256(
        f"{cluster_key}|{cluster_time.date().isoformat()}|"
        f"{normalized_title.casefold()}"
    )
    occurrence_id = _sha256(
        "|".join(
            (
                document.publisher.casefold(),
                document.document_id,
                document.source_record_id or "",
                document.retrieved_at.isoformat(),
            )
        )
    )

    return SanitizedNewsDocumentV1(
        occurrence_id=occurrence_id,
        source_document_id=document.document_id,
        publisher=document.publisher,
        authority=document.authority,
        published_at=document.published_at,
        retrieved_at=document.retrieved_at,
        event_at=document.event_at,
        title=normalized_title,
        sanitized_text=sanitized_text,
        content_kind=document.content_kind,
        entity_resolution=document.entity_resolution,
        instrument_key=document.instrument_key,
        disposition=_disposition(document=document, flags=flags_tuple),
        injection_flags=flags_tuple,
        content_fingerprint=content_fingerprint,
        event_cluster_id=event_cluster_id,
        truncated=truncated,
        raw_content_stored=False,
        trading_methods=False,
    )


def _canonical_rank(
    document: SanitizedNewsDocumentV1,
) -> tuple[int, int, int, float]:
    disposition_rank = {
        NewsDisposition.ACCEPTED: 3,
        NewsDisposition.CONTEXT_ONLY: 2,
        NewsDisposition.REJECTED: 1,
    }[document.disposition]
    authority_rank = {
        SourceAuthority.PRIMARY: 5,
        SourceAuthority.OFFICIAL: 4,
        SourceAuthority.REGULATED: 3,
        SourceAuthority.SECONDARY: 2,
        SourceAuthority.UNTRUSTED: 1,
    }[document.authority]
    kind_rank = {
        NewsContentKind.FACT: 4,
        NewsContentKind.MIXED: 3,
        NewsContentKind.OPINION: 2,
        NewsContentKind.FORECAST: 1,
    }[document.content_kind]
    return (
        disposition_rank,
        authority_rank,
        kind_rank,
        -document.published_at.timestamp(),
    )


def deduplicate_news_documents(
    documents: Iterable[SanitizedNewsDocumentV1],
) -> NewsDeduplicationResultV1:
    """Collapse exact sanitized-content duplicates deterministically."""
    rows = tuple(documents)
    by_fingerprint: dict[str, list[SanitizedNewsDocumentV1]] = {}
    for document in rows:
        by_fingerprint.setdefault(
            document.content_fingerprint,
            [],
        ).append(document)

    canonical_documents: list[SanitizedNewsDocumentV1] = []
    duplicates: list[DuplicateNewsOccurrenceV1] = []
    for fingerprint, group in sorted(by_fingerprint.items()):
        canonical = max(group, key=_canonical_rank)
        canonical_documents.append(canonical)
        for duplicate_index, duplicate in enumerate(group):
            if duplicate is canonical:
                continue
            duplicate_occurrence_id = duplicate.occurrence_id
            if duplicate_occurrence_id == canonical.occurrence_id:
                duplicate_occurrence_id = _sha256(
                    f"{duplicate_occurrence_id}|duplicate|{duplicate_index}"
                )
            duplicates.append(
                DuplicateNewsOccurrenceV1(
                    content_fingerprint=fingerprint,
                    canonical_occurrence_id=canonical.occurrence_id,
                    duplicate_occurrence_id=duplicate_occurrence_id,
                )
            )

    canonical_documents.sort(
        key=lambda document: (
            document.published_at,
            document.occurrence_id,
        )
    )
    duplicates.sort(
        key=lambda duplicate: (
            duplicate.content_fingerprint,
            duplicate.duplicate_occurrence_id,
        )
    )
    return NewsDeduplicationResultV1(
        canonical_documents=tuple(canonical_documents),
        duplicates=tuple(duplicates),
        input_count=len(rows),
        canonical_count=len(canonical_documents),
        duplicate_count=len(duplicates),
    )
