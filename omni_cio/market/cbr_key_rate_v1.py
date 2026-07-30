from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import re
from xml.etree import ElementTree
from xml.parsers import expat

import httpx

from omni_cio.contracts.v1.macro import (
    CbrKeyRateSnapshotV1,
    KeyRateObservationV1,
    MacroDataErrorCode,
    MacroDataStatus,
)
from omni_cio.contracts.v1.market import MarketSourceV1, SourceAuthority


CBR_KEY_RATE_ENDPOINT = "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"
CBR_KEY_RATE_SOAP_ACTION = "http://web.cbr.ru/KeyRateXML"
CBR_KEY_RATE_PROVIDER = "Bank of Russia DailyInfo"
CBR_KEY_RATE_SOURCE_ID = "DailyInfo.KeyRateXML"
DEFAULT_CBR_KEY_RATE_TIMEOUT_SECONDS = 10.0
DEFAULT_CBR_KEY_RATE_MAX_RESPONSE_BYTES = 1_000_000
MAX_CBR_KEY_RATE_RANGE_DAYS = 3_660

_ALLOWED_CONTENT_TYPES = {
    "application/xml",
    "application/soap+xml",
    "text/xml",
}
_DATE_FIELDS = (
    "dt",
    "date",
    "effectivedate",
    "datefrom",
    "fromdate",
)
_RATE_FIELDS = (
    "rate",
    "keyrate",
    "value",
)
_XML_DECLARATION_RISK = re.compile(
    br"<!\s*(?:DOCTYPE|ENTITY)\b",
    re.IGNORECASE,
)


class CbrKeyRateSourceError(ValueError):
    """The official CBR key-rate payload cannot be handled safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise CbrKeyRateSourceError("CBR_KEY_RATE_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _validate_request_range(
    requested_from: date,
    requested_to: date,
    *,
    retrieved_at: datetime,
) -> None:
    if not isinstance(requested_from, date) or not isinstance(requested_to, date):
        raise CbrKeyRateSourceError("CBR_KEY_RATE_DATE_RANGE_INVALID")
    if requested_from > requested_to:
        raise CbrKeyRateSourceError("CBR_KEY_RATE_DATE_RANGE_INVALID")
    if (requested_to - requested_from).days > MAX_CBR_KEY_RATE_RANGE_DAYS:
        raise CbrKeyRateSourceError("CBR_KEY_RATE_DATE_RANGE_TOO_LARGE")
    if requested_to > retrieved_at.date():
        raise CbrKeyRateSourceError("CBR_KEY_RATE_DATE_RANGE_FROM_FUTURE")


def build_cbr_key_rate_soap_request(
    requested_from: date,
    requested_to: date,
) -> bytes:
    """Build the fixed SOAP 1.1 request accepted by the official CBR service."""
    if requested_from > requested_to:
        raise CbrKeyRateSourceError("CBR_KEY_RATE_DATE_RANGE_INVALID")
    from_value = requested_from.isoformat()
    to_value = requested_to.isoformat()
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soap:Body><KeyRateXML xmlns="http://web.cbr.ru/">'
        f"<fromDate>{from_value}T00:00:00</fromDate>"
        f"<ToDate>{to_value}T23:59:59</ToDate>"
        "</KeyRateXML></soap:Body></soap:Envelope>"
    ).encode("utf-8")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _parse_xml_document(payload: bytes) -> ElementTree.Element:
    if not payload or _XML_DECLARATION_RISK.search(payload):
        raise CbrKeyRateSourceError(MacroDataErrorCode.XML_INVALID.value)

    parser = expat.ParserCreate(namespace_separator="}")
    parser.buffer_text = True
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    stack: list[ElementTree.Element] = []
    root: ElementTree.Element | None = None

    def start_element(name: str, attributes: dict[str, str]) -> None:
        nonlocal root
        element = ElementTree.Element(name, attributes)
        if stack:
            stack[-1].append(element)
        else:
            root = element
        stack.append(element)

    def end_element(name: str) -> None:
        if not stack or stack[-1].tag != name:
            raise CbrKeyRateSourceError(MacroDataErrorCode.XML_INVALID.value)
        stack.pop()

    def character_data(data: str) -> None:
        if stack:
            stack[-1].text = (stack[-1].text or "") + data

    def reject_declaration(*args: object) -> None:
        raise CbrKeyRateSourceError(MacroDataErrorCode.XML_INVALID.value)

    def reject_external_entity(*args: object) -> int:
        raise CbrKeyRateSourceError(MacroDataErrorCode.XML_INVALID.value)

    parser.StartElementHandler = start_element
    parser.EndElementHandler = end_element
    parser.CharacterDataHandler = character_data
    parser.StartDoctypeDeclHandler = reject_declaration
    parser.EntityDeclHandler = reject_declaration
    parser.ExternalEntityRefHandler = reject_external_entity

    try:
        parser.Parse(payload, True)
    except CbrKeyRateSourceError:
        raise
    except expat.ExpatError as exc:
        raise CbrKeyRateSourceError(
            MacroDataErrorCode.XML_INVALID.value
        ) from exc
    if root is None or stack:
        raise CbrKeyRateSourceError(MacroDataErrorCode.XML_INVALID.value)
    return root


def _parse_date(value: str) -> date:
    text = value.strip()
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        pass
    for pattern in ("%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise CbrKeyRateSourceError(MacroDataErrorCode.XML_INVALID.value)


def _parse_rate(value: str) -> Decimal:
    text = value.strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise CbrKeyRateSourceError(
            MacroDataErrorCode.XML_INVALID.value
        ) from exc
    if not result.is_finite() or result < Decimal("0") or result > Decimal("100"):
        raise CbrKeyRateSourceError(MacroDataErrorCode.XML_INVALID.value)
    return result


def _find_result_element(root: ElementTree.Element) -> ElementTree.Element:
    for element in root.iter():
        if _local_name(element.tag) == "keyratexmlresult":
            return element
    raise CbrKeyRateSourceError(MacroDataErrorCode.XML_INVALID.value)


def _data_roots(result: ElementTree.Element) -> tuple[ElementTree.Element, ...]:
    children = tuple(result)
    if children:
        return children
    text = (result.text or "").strip()
    if not text:
        raise CbrKeyRateSourceError(MacroDataErrorCode.EMPTY.value)
    return (_parse_xml_document(text.encode("utf-8")),)


def _row_values(element: ElementTree.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for child in element:
        if len(child):
            continue
        text = (child.text or "").strip()
        if text:
            values[_local_name(child.tag)] = text
    return values


def _observation_pairs(
    roots: Iterable[ElementTree.Element],
) -> tuple[tuple[date, Decimal], ...]:
    observations: dict[date, Decimal] = {}
    for root in roots:
        for element in root.iter():
            values = _row_values(element)
            date_value = next(
                (values[name] for name in _DATE_FIELDS if name in values),
                None,
            )
            rate_value = next(
                (values[name] for name in _RATE_FIELDS if name in values),
                None,
            )
            if date_value is None or rate_value is None:
                continue
            effective_date = _parse_date(date_value)
            rate = _parse_rate(rate_value)
            previous = observations.get(effective_date)
            if previous is not None and previous != rate:
                raise CbrKeyRateSourceError(
                    MacroDataErrorCode.DUPLICATE_CONFLICT.value
                )
            observations[effective_date] = rate
    return tuple(sorted(observations.items(), key=lambda item: item[0]))


def parse_cbr_key_rate_xml(
    payload: bytes,
    *,
    requested_from: date,
    requested_to: date,
    retrieved_at: datetime | None = None,
) -> CbrKeyRateSnapshotV1:
    """Parse one bounded SOAP response as data without retaining raw XML."""
    observed_at = _aware_utc(retrieved_at)
    _validate_request_range(
        requested_from,
        requested_to,
        retrieved_at=observed_at,
    )
    if not isinstance(payload, bytes) or not payload:
        raise CbrKeyRateSourceError(MacroDataErrorCode.EMPTY.value)

    root = _parse_xml_document(payload)
    if any(_local_name(element.tag) == "fault" for element in root.iter()):
        raise CbrKeyRateSourceError(MacroDataErrorCode.SOAP_FAULT.value)

    result = _find_result_element(root)
    pairs = _observation_pairs(_data_roots(result))
    if not pairs:
        raise CbrKeyRateSourceError(MacroDataErrorCode.EMPTY.value)
    if any(
        effective_date < requested_from or effective_date > requested_to
        for effective_date, _ in pairs
    ):
        raise CbrKeyRateSourceError(MacroDataErrorCode.RANGE_MISMATCH.value)

    observations = tuple(
        KeyRateObservationV1(
            effective_date=effective_date,
            rate_percent=rate,
        )
        for effective_date, rate in pairs
    )
    source = MarketSourceV1(
        provider=CBR_KEY_RATE_PROVIDER,
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=observed_at,
        source_id=CBR_KEY_RATE_SOURCE_ID,
    )
    return CbrKeyRateSnapshotV1(
        requested_from=requested_from,
        requested_to=requested_to,
        retrieved_at=observed_at,
        status=MacroDataStatus.AVAILABLE,
        source=source,
        observations=observations,
        current=observations[-1],
    )


def _unavailable_snapshot(
    *,
    requested_from: date,
    requested_to: date,
    retrieved_at: datetime,
    error_code: MacroDataErrorCode,
) -> CbrKeyRateSnapshotV1:
    return CbrKeyRateSnapshotV1(
        requested_from=requested_from,
        requested_to=requested_to,
        retrieved_at=retrieved_at,
        status=MacroDataStatus.UNAVAILABLE,
        error_code=error_code,
        warnings=("Official CBR key-rate data is unavailable.",),
    )


def _mapped_error_code(error: CbrKeyRateSourceError) -> MacroDataErrorCode:
    try:
        return MacroDataErrorCode(str(error))
    except ValueError:
        return MacroDataErrorCode.XML_INVALID


def _read_bounded_response(
    active_client: httpx.Client,
    *,
    body: bytes,
    headers: dict[str, str],
    timeout_seconds: float,
    max_response_bytes: int,
) -> tuple[int, str, bytes, bool]:
    with active_client.stream(
        "POST",
        CBR_KEY_RATE_ENDPOINT,
        content=body,
        headers=headers,
        timeout=timeout_seconds,
        follow_redirects=False,
    ) as response:
        content_type = (
            response.headers.get("content-type", "")
            .partition(";")[0]
            .strip()
            .lower()
        )
        if response.status_code != 200 or content_type not in _ALLOWED_CONTENT_TYPES:
            return response.status_code, content_type, b"", False

        declared_length = response.headers.get("content-length")
        if declared_length is not None:
            try:
                if int(declared_length) > max_response_bytes:
                    return response.status_code, content_type, b"", True
            except ValueError:
                pass

        payload = bytearray()
        for chunk in response.iter_bytes():
            if len(payload) + len(chunk) > max_response_bytes:
                return response.status_code, content_type, b"", True
            payload.extend(chunk)
        return response.status_code, content_type, bytes(payload), False


def fetch_cbr_key_rate(
    *,
    requested_from: date,
    requested_to: date,
    retrieved_at: datetime | None = None,
    client: httpx.Client | None = None,
    timeout_seconds: float = DEFAULT_CBR_KEY_RATE_TIMEOUT_SECONDS,
    max_response_bytes: int = DEFAULT_CBR_KEY_RATE_MAX_RESPONSE_BYTES,
) -> CbrKeyRateSnapshotV1:
    """Fetch key-rate history from one fixed official endpoint, fail closed."""
    observed_at = _aware_utc(retrieved_at)
    _validate_request_range(
        requested_from,
        requested_to,
        retrieved_at=observed_at,
    )
    if not 0.1 <= timeout_seconds <= 30.0:
        raise CbrKeyRateSourceError("CBR_KEY_RATE_TIMEOUT_INVALID")
    if not 1_024 <= max_response_bytes <= 5_000_000:
        raise CbrKeyRateSourceError("CBR_KEY_RATE_RESPONSE_LIMIT_INVALID")

    body = build_cbr_key_rate_soap_request(requested_from, requested_to)
    headers = {
        "Accept": "application/xml, text/xml",
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{CBR_KEY_RATE_SOAP_ACTION}"',
        "User-Agent": "omni-cio-gateway/readonly-cbr-key-rate-v1",
    }

    try:
        if client is None:
            with httpx.Client(
                timeout=timeout_seconds,
                verify=True,
                follow_redirects=False,
            ) as owned_client:
                status_code, content_type, payload, too_large = (
                    _read_bounded_response(
                        owned_client,
                        body=body,
                        headers=headers,
                        timeout_seconds=timeout_seconds,
                        max_response_bytes=max_response_bytes,
                    )
                )
        else:
            status_code, content_type, payload, too_large = _read_bounded_response(
                client,
                body=body,
                headers=headers,
                timeout_seconds=timeout_seconds,
                max_response_bytes=max_response_bytes,
            )
    except httpx.HTTPError:
        return _unavailable_snapshot(
            requested_from=requested_from,
            requested_to=requested_to,
            retrieved_at=observed_at,
            error_code=MacroDataErrorCode.NETWORK_ERROR,
        )

    if status_code != 200:
        return _unavailable_snapshot(
            requested_from=requested_from,
            requested_to=requested_to,
            retrieved_at=observed_at,
            error_code=MacroDataErrorCode.HTTP_ERROR,
        )
    if content_type not in _ALLOWED_CONTENT_TYPES:
        return _unavailable_snapshot(
            requested_from=requested_from,
            requested_to=requested_to,
            retrieved_at=observed_at,
            error_code=MacroDataErrorCode.CONTENT_TYPE_INVALID,
        )
    if too_large:
        return _unavailable_snapshot(
            requested_from=requested_from,
            requested_to=requested_to,
            retrieved_at=observed_at,
            error_code=MacroDataErrorCode.RESPONSE_TOO_LARGE,
        )
    try:
        return parse_cbr_key_rate_xml(
            payload,
            requested_from=requested_from,
            requested_to=requested_to,
            retrieved_at=observed_at,
        )
    except CbrKeyRateSourceError as exc:
        return _unavailable_snapshot(
            requested_from=requested_from,
            requested_to=requested_to,
            retrieved_at=observed_at,
            error_code=_mapped_error_code(exc),
        )
