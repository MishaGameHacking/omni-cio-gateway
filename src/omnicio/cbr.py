"""Bank of Russia public reference-data adapter."""

from __future__ import annotations

import logging
import re
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html import unescape
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_CBR_DAILY_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
_MOSCOW = ZoneInfo("Europe/Moscow")
_INDICATOR_CURRENCIES = frozenset({"USD", "EUR"})
_MAX_PUBLIC_RESPONSE_BYTES = 512_000
_CBR_XML_ACCEPT = "application/xml,text/xml;q=0.9,*/*;q=0.1"
_CBR_USER_AGENT = "OmniCIO-Personal/1.0"


class CBRUnavailable(RuntimeError):
    """The Bank of Russia public data feed is unavailable or malformed."""


@dataclass(frozen=True, slots=True)
class CBRRate:
    currency: str
    value: str
    nominal: int
    effective_date: date
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class CBRKeyRate:
    value: str
    effective_date: date
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class CBRIndicators:
    usd_rub: CBRRate
    eur_rub: CBRRate
    key_rate: CBRKeyRate
    fetched_at: datetime
    freshness: str


# Fixed public reference series, not exchange prices or a broker fallback.
_HISTORY_CURRENCIES = {"USD": "R01235", "EUR": "R01239", "CNY": "R01375"}
_HISTORY_PERIODS = {"1m": 31, "3m": 93, "1y": 365}


@dataclass(frozen=True, slots=True)
class CBRHistoryPoint:
    effective_date: str
    value: str


@dataclass(frozen=True, slots=True)
class CBRHistory:
    currency: str
    period: str
    from_date: str
    to_date: str
    fetched_at: str
    source_url: str
    freshness: str
    points: tuple[CBRHistoryPoint, ...]


class CBRClient:
    def __init__(
        self,
        *,
        timeout_seconds: int = 6,
        cache_seconds: int = 3600,
        indicator_cache_seconds: int = 300,
        failure_retry_seconds: int = 300,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.cache_seconds = cache_seconds
        self.indicator_cache_seconds = indicator_cache_seconds
        self.failure_retry_seconds = failure_retry_seconds
        self._lock = threading.Lock()
        self._cached: dict[str, CBRRate] = {}
        self._expires_at: dict[str, float] = {}
        self._retry_after: dict[str, float] = {}
        self._indicator_cached: CBRIndicators | None = None
        self._indicator_expires_at = 0.0
        self._indicator_retry_after = 0.0
        self._history_lock = threading.Lock()
        self._history_cache: dict[tuple[str, str], CBRHistory] = {}
        self._history_expires: dict[tuple[str, str], float] = {}
        self._history_retry: dict[tuple[str, str], float] = {}

    def usd_rub_rate(self, effective_on: date | None = None) -> CBRRate:
        target = effective_on or datetime.now(_MOSCOW).date()
        return self._cached_rate(
            key=f"date:{target.isoformat()}",
            effective_on=target,
        )

    def latest_usd_rub_rate(self) -> CBRRate:
        return self._cached_rate(key="latest", effective_on=None)

    def latest_indicators(self) -> CBRIndicators:
        now = time.monotonic()
        cached = self._indicator_cached
        if cached is not None and now < self._indicator_expires_at:
            return cached
        if cached is None and now < self._indicator_retry_after:
            raise CBRUnavailable("Bank of Russia indicator retry is pending")

        with self._lock:
            now = time.monotonic()
            cached = self._indicator_cached
            if cached is not None and now < self._indicator_expires_at:
                return cached
            if cached is None and now < self._indicator_retry_after:
                raise CBRUnavailable("Bank of Russia indicator retry is pending")

            try:
                rates = self._fetch_latest_indicator_rates()
                key_rate = self._fetch_key_rate()
            except CBRUnavailable:
                self._indicator_retry_after = now + self.failure_retry_seconds
                if cached is not None:
                    logger.warning(
                        "Bank of Russia indicator refresh failed; using cached values"
                    )
                    fallback = CBRIndicators(
                        usd_rub=cached.usd_rub,
                        eur_rub=cached.eur_rub,
                        key_rate=cached.key_rate,
                        fetched_at=cached.fetched_at,
                        freshness="cached",
                    )
                    self._indicator_cached = fallback
                    self._indicator_expires_at = (
                        now
                        + min(
                            self.indicator_cache_seconds,
                            self.failure_retry_seconds,
                        )
                    )
                    return fallback
                raise

            fetched_at = max(
                rates["USD"].fetched_at,
                rates["EUR"].fetched_at,
                key_rate.fetched_at,
            )
            indicators = CBRIndicators(
                usd_rub=rates["USD"],
                eur_rub=rates["EUR"],
                key_rate=key_rate,
                fetched_at=fetched_at,
                freshness="fresh",
            )
            self._indicator_cached = indicators
            self._indicator_expires_at = now + self.indicator_cache_seconds
            self._indicator_retry_after = 0.0
            return indicators

    def reference_history(self, currency: str, period: str) -> CBRHistory:
        """Read at most nine fixed cache keys, without account data or arbitrary URLs."""
        if currency not in _HISTORY_CURRENCIES or period not in _HISTORY_PERIODS:
            raise ValueError("unsupported reference history")
        key = (currency, period)
        target = datetime.now(_MOSCOW).date()
        now = time.monotonic()
        cached = self._history_cache.get(key)
        if (cached is not None and cached.to_date == target.isoformat()
                and now < self._history_expires.get(key, 0)):
            return cached
        if now < self._history_retry.get(key, 0):
            if cached is not None:
                return replace(cached, freshness="cached")
            raise CBRUnavailable("Bank of Russia history retry is pending")
        if not self._history_lock.acquire(blocking=False):
            if cached is not None:
                return replace(cached, freshness="cached")
            raise CBRUnavailable("Bank of Russia history refresh is in progress")
        try:
            # Recheck after acquisition: another thread may have just completed.
            cached = self._history_cache.get(key)
            now = time.monotonic()
            if (cached is not None and cached.to_date == target.isoformat()
                    and now < self._history_expires.get(key, 0)):
                return cached
            try:
                result = self._fetch_reference_history(currency, period, target)
            except CBRUnavailable:
                self._history_retry[key] = time.monotonic() + self.failure_retry_seconds
                if cached is not None:
                    return replace(cached, freshness="cached")
                raise
            self._history_cache[key] = result
            self._history_expires[key] = time.monotonic() + self.cache_seconds
            self._history_retry[key] = 0
            return result
        finally:
            self._history_lock.release()

    def _fetch_reference_history(self, currency: str, period: str, target: date) -> CBRHistory:
        start = target - timedelta(days=_HISTORY_PERIODS[period])
        code = _HISTORY_CURRENCIES[currency]
        url = ("https://www.cbr.ru/scripts/XML_dynamic.asp"
               f"?date_req1={start.strftime('%d/%m/%Y')}"
               f"&date_req2={target.strftime('%d/%m/%Y')}&VAL_NM_RQ={code}")
        request = urllib.request.Request(url, headers={
            "Accept": _CBR_XML_ACCEPT, "User-Agent": _CBR_USER_AGENT,
        })
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = response.read(_MAX_PUBLIC_RESPONSE_BYTES + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise CBRUnavailable("Bank of Russia history unavailable") from exc
        points = _parse_reference_history(payload, code=code, start=start, end=target)
        return CBRHistory(
            currency=currency, period=period, from_date=start.isoformat(),
            to_date=target.isoformat(), fetched_at=datetime.now(UTC).isoformat(),
            source_url=url, freshness="received", points=points,
        )

    def _cached_rate(
        self,
        *,
        key: str,
        effective_on: date | None,
    ) -> CBRRate:
        now = time.monotonic()
        cached = self._cached.get(key)
        if cached is not None and now < self._expires_at.get(key, 0.0):
            return cached
        if cached is None and now < self._retry_after.get(key, 0.0):
            raise CBRUnavailable("Bank of Russia daily rate retry is pending")

        with self._lock:
            now = time.monotonic()
            cached = self._cached.get(key)
            if cached is not None and now < self._expires_at.get(key, 0.0):
                return cached
            if cached is None and now < self._retry_after.get(key, 0.0):
                raise CBRUnavailable("Bank of Russia daily rate retry is pending")

            try:
                rate = self._fetch_usd_rub(effective_on)
            except CBRUnavailable:
                self._retry_after[key] = now + self.failure_retry_seconds
                if cached is not None:
                    logger.warning(
                        "Bank of Russia rate refresh failed key=%s; using cached value",
                        key,
                    )
                    self._expires_at[key] = (
                        now + min(self.cache_seconds, self.failure_retry_seconds)
                    )
                    return cached
                raise

            self._cached[key] = rate
            self._expires_at[key] = now + self.cache_seconds
            self._retry_after[key] = 0.0
            return rate

    def _fetch_usd_rub(self, effective_on: date | None) -> CBRRate:
        url = _CBR_DAILY_URL
        if effective_on is not None:
            url = f"{url}?date_req={effective_on.strftime('%d/%m/%Y')}"

        request = urllib.request.Request(
            url,
            headers={
                "Accept": _CBR_XML_ACCEPT,
                "User-Agent": _CBR_USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                payload = response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.warning(
                "Bank of Russia daily-rate request failed reason=%s",
                type(getattr(exc, "reason", exc)).__name__,
            )
            raise CBRUnavailable("Bank of Russia daily rate unavailable") from exc

        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise CBRUnavailable("Bank of Russia returned invalid XML") from exc

        effective_date = _parse_effective_date(root.attrib.get("Date", ""))
        for valute in root.findall("Valute"):
            char_code = (valute.findtext("CharCode") or "").strip().upper()
            if char_code != "USD":
                continue

            nominal_text = (valute.findtext("Nominal") or "").strip()
            value_text = (valute.findtext("Value") or "").strip().replace(",", ".")
            try:
                nominal = int(nominal_text)
                value = Decimal(value_text)
            except (InvalidOperation, ValueError) as exc:
                raise CBRUnavailable("Bank of Russia returned invalid USD rate") from exc
            if nominal <= 0:
                raise CBRUnavailable("Bank of Russia returned invalid USD nominal")

            per_unit = value / Decimal(nominal)
            return CBRRate(
                currency="RUB",
                value=format(per_unit.normalize(), "f"),
                nominal=1,
                effective_date=effective_date,
                fetched_at=datetime.now(UTC),
            )

        raise CBRUnavailable("Bank of Russia response has no USD rate")

    def _fetch_latest_indicator_rates(self) -> dict[str, CBRRate]:
        request = urllib.request.Request(
            "https://www.cbr.ru/scripts/XML_daily.asp",
            headers={
                "Accept": _CBR_XML_ACCEPT,
                "User-Agent": _CBR_USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                payload = response.read(_MAX_PUBLIC_RESPONSE_BYTES + 1)
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.warning(
                "Bank of Russia indicator currency request failed reason=%s",
                type(getattr(exc, "reason", exc)).__name__,
            )
            raise CBRUnavailable("Bank of Russia currency indicators unavailable") from exc
        if len(payload) > _MAX_PUBLIC_RESPONSE_BYTES:
            raise CBRUnavailable("Bank of Russia currency response is too large")

        parser = _CurrencyIndicatorParser()
        try:
            parser.feed(payload.decode("windows-1251"))
            parser.close()
        except ValueError as exc:
            raise CBRUnavailable("Bank of Russia returned invalid currency data") from exc
        return parser.result()

    def _fetch_key_rate(self) -> CBRKeyRate:
        target = datetime.now(_MOSCOW).date()
        from_date = target - timedelta(days=14)
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema"
 xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <KeyRateXML xmlns="http://web.cbr.ru/">
      <fromDate>{from_date.isoformat()}T00:00:00</fromDate>
      <ToDate>{target.isoformat()}T23:59:59</ToDate>
    </KeyRateXML>
  </soap:Body>
</soap:Envelope>
""".encode()
        request = urllib.request.Request(
            "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx",
            data=body,
            method="POST",
            headers={
                "Accept": _CBR_XML_ACCEPT,
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": '"http://web.cbr.ru/KeyRateXML"',
                "User-Agent": _CBR_USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                payload = response.read(_MAX_PUBLIC_RESPONSE_BYTES + 1)
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.warning(
                "Bank of Russia key-rate request failed reason=%s",
                type(getattr(exc, "reason", exc)).__name__,
            )
            raise CBRUnavailable("Bank of Russia key rate unavailable") from exc
        if len(payload) > _MAX_PUBLIC_RESPONSE_BYTES:
            raise CBRUnavailable("Bank of Russia key-rate response is too large")

        try:
            document = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CBRUnavailable("Bank of Russia returned invalid key-rate encoding") from exc
        candidates = _parse_key_rate_document(document)
        eligible = [item for item in candidates if item[0] <= target]
        if not eligible:
            raise CBRUnavailable("Bank of Russia response has no current key rate")
        effective_date, value = max(eligible, key=lambda item: item[0])
        return CBRKeyRate(
            value=value,
            effective_date=effective_date,
            fetched_at=datetime.now(UTC),
        )


class _CurrencyIndicatorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.effective_date = ""
        self._in_valute = False
        self._field: str | None = None
        self._current: dict[str, str] = {}
        self._rows: list[dict[str, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag == "valcurs":
            attributes = dict(attrs)
            self.effective_date = (attributes.get("date") or "").strip()
        elif tag == "valute":
            if self._in_valute:
                raise ValueError("nested Valute element")
            self._in_valute = True
            self._current = {}
        elif self._in_valute and tag in {"charcode", "nominal", "value"}:
            self._field = tag

    def handle_data(self, data: str) -> None:
        if self._in_valute and self._field is not None:
            self._current[self._field] = self._current.get(self._field, "") + data

    def handle_endtag(self, tag: str) -> None:
        if tag == self._field:
            self._field = None
        if tag == "valute":
            if not self._in_valute:
                raise ValueError("unexpected Valute end")
            self._rows.append(self._current)
            self._current = {}
            self._in_valute = False
            self._field = None

    def result(self) -> dict[str, CBRRate]:
        effective_date = _parse_effective_date(self.effective_date)
        fetched_at = datetime.now(UTC)
        result: dict[str, CBRRate] = {}
        for row in self._rows:
            char_code = row.get("charcode", "").strip().upper()
            if char_code not in _INDICATOR_CURRENCIES:
                continue
            if char_code in result:
                raise CBRUnavailable(
                    f"Bank of Russia returned duplicate {char_code} rate"
                )
            nominal_text = row.get("nominal", "").strip()
            value_text = row.get("value", "").strip().replace(",", ".")
            try:
                nominal = int(nominal_text)
                value = Decimal(value_text)
            except (InvalidOperation, ValueError) as exc:
                raise CBRUnavailable(
                    f"Bank of Russia returned invalid {char_code} rate"
                ) from exc
            if nominal <= 0 or not value.is_finite() or value <= 0:
                raise CBRUnavailable(
                    f"Bank of Russia returned invalid {char_code} value"
                )
            result[char_code] = CBRRate(
                currency="RUB",
                value=format((value / Decimal(nominal)).normalize(), "f"),
                nominal=1,
                effective_date=effective_date,
                fetched_at=fetched_at,
            )

        missing = _INDICATOR_CURRENCIES.difference(result)
        if missing:
            raise CBRUnavailable(
                "Bank of Russia response is missing currency rate: "
                + ",".join(sorted(missing))
            )
        return result


class _KeyRateParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_row = False
        self._field: str | None = None
        self._current: dict[str, str] = {}
        self.rows: list[tuple[date, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if tag == "kr":
            if self._in_row:
                raise ValueError("nested key-rate row")
            self._in_row = True
            self._current = {}
        elif self._in_row and tag in {"dt", "rate"}:
            self._field = tag

    def handle_data(self, data: str) -> None:
        if self._in_row and self._field is not None:
            self._current[self._field] = self._current.get(self._field, "") + data

    def handle_endtag(self, tag: str) -> None:
        if tag == self._field:
            self._field = None
        if tag != "kr":
            return
        if not self._in_row:
            raise ValueError("unexpected key-rate row end")
        date_text = self._current.get("dt", "").strip()
        rate_text = self._current.get("rate", "").strip().replace(",", ".")
        try:
            effective_date = datetime.fromisoformat(
                date_text.replace("Z", "+00:00")
            ).date()
            rate = Decimal(rate_text)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("invalid key-rate row") from exc
        if not rate.is_finite() or rate <= 0:
            raise ValueError("invalid key-rate value")
        self.rows.append((effective_date, format(rate.normalize(), "f")))
        self._current = {}
        self._in_row = False
        self._field = None


class _SoapResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture = False
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if tag == "keyratexmlresult":
            self._capture = True

    def handle_data(self, data: str) -> None:
        if self._capture:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "keyratexmlresult":
            self._capture = False


def _parse_key_rate_document(document: str) -> list[tuple[date, str]]:
    direct = _KeyRateParser()
    try:
        direct.feed(document)
        direct.close()
    except ValueError as exc:
        raise CBRUnavailable("Bank of Russia returned invalid key-rate data") from exc
    if direct.rows:
        return direct.rows

    result = _SoapResultParser()
    result.feed(document)
    result.close()
    embedded = unescape("".join(result.parts)).strip()
    if not embedded:
        return []

    nested = _KeyRateParser()
    try:
        nested.feed(embedded)
        nested.close()
    except ValueError as exc:
        raise CBRUnavailable("Bank of Russia returned invalid embedded key-rate data") from exc
    return nested.rows


def _parse_effective_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError as exc:
        raise CBRUnavailable("Bank of Russia returned invalid rate date") from exc


def _parse_reference_history(
    payload: bytes, *, code: str, start: date, end: date,
) -> tuple[CBRHistoryPoint, ...]:
    """Preserve effective dates and per-unit Decimal values, never fill missing days."""
    if (len(payload) > _MAX_PUBLIC_RESPONSE_BYTES
            or b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper()):
        raise CBRUnavailable("Bank of Russia history payload is invalid")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise CBRUnavailable("Bank of Russia history XML is invalid") from exc
    if root.tag != "ValCurs" or root.attrib.get("ID") != code or len(root) > 370:
        raise CBRUnavailable("Bank of Russia history identity is invalid")
    values: dict[date, str] = {}
    for record in root:
        if record.tag != "Record" or record.attrib.get("Id") != code:
            raise CBRUnavailable("Bank of Russia history record is invalid")
        try:
            effective = datetime.strptime(record.attrib["Date"], "%d.%m.%Y").date()
            nominal_text = (record.findtext("Nominal") or "").strip()
            value_text = (record.findtext("Value") or "").strip()
            if (not re.fullmatch(r"[0-9]{1,9}", nominal_text)
                    or not re.fullmatch(r"[0-9]{1,12}(?:[.,][0-9]{1,9})?", value_text)):
                raise ValueError("invalid source decimal representation")
            nominal = Decimal(nominal_text)
            value = Decimal(value_text.replace(",", "."))
        except (KeyError, ValueError, InvalidOperation) as exc:
            raise CBRUnavailable("Bank of Russia history value is invalid") from exc
        if (not start <= effective <= end or not nominal.is_finite() or nominal <= 0
                or nominal != nominal.to_integral_value() or not value.is_finite()
                or value <= 0 or value > 1000000000 or nominal > 1000000000):
            raise CBRUnavailable("Bank of Russia history bounds are invalid")
        per_unit = format((value / nominal).normalize(), "f")
        if effective in values and values[effective] != per_unit:
            raise CBRUnavailable("Bank of Russia history has conflicting records")
        values[effective] = per_unit
    return tuple(CBRHistoryPoint(day.isoformat(), values[day]) for day in sorted(values))
