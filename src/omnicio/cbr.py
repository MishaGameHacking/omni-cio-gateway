"""Bank of Russia public reference-data adapter."""

from __future__ import annotations

import logging
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_CBR_DAILY_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
_CBR_DAILY_INFO_URL = "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"
_CBR_KEY_RATE_ACTION = "http://web.cbr.ru/KeyRateXML"
_MOSCOW = ZoneInfo("Europe/Moscow")
_INDICATOR_CURRENCIES = frozenset({"USD", "EUR"})


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
                rates = self._fetch_currency_rates(
                    effective_on=None,
                    codes=_INDICATOR_CURRENCIES,
                )
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
        return self._fetch_currency_rates(
            effective_on=effective_on,
            codes=frozenset({"USD"}),
        )["USD"]

    def _fetch_currency_rates(
        self,
        *,
        effective_on: date | None,
        codes: frozenset[str],
    ) -> dict[str, CBRRate]:
        if not codes or not codes.issubset(_INDICATOR_CURRENCIES):
            raise CBRUnavailable("Unsupported Bank of Russia currency request")

        url = _CBR_DAILY_URL
        if effective_on is not None:
            url = f"{url}?date_req={effective_on.strftime('%d/%m/%Y')}"

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.1",
                "User-Agent": "OmniCIO-Personal/1.0",
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
            raise CBRUnavailable("Bank of Russia returned invalid daily-rate XML") from exc

        effective_date = _parse_effective_date(root.attrib.get("Date", ""))
        fetched_at = datetime.now(UTC)
        result: dict[str, CBRRate] = {}
        for valute in root.findall("Valute"):
            char_code = (valute.findtext("CharCode") or "").strip().upper()
            if char_code not in codes:
                continue

            nominal_text = (valute.findtext("Nominal") or "").strip()
            value_text = (valute.findtext("Value") or "").strip().replace(",", ".")
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

            per_unit = value / Decimal(nominal)
            result[char_code] = CBRRate(
                currency="RUB",
                value=format(per_unit.normalize(), "f"),
                nominal=1,
                effective_date=effective_date,
                fetched_at=fetched_at,
            )

        missing = codes.difference(result)
        if missing:
            missing_codes = ",".join(sorted(missing))
            raise CBRUnavailable(
                f"Bank of Russia response is missing currency rate: {missing_codes}"
            )
        return result

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
            _CBR_DAILY_INFO_URL,
            data=body,
            method="POST",
            headers={
                "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.1",
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": f'"{_CBR_KEY_RATE_ACTION}"',
                "User-Agent": "OmniCIO-Personal/1.0",
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
                "Bank of Russia key-rate request failed reason=%s",
                type(getattr(exc, "reason", exc)).__name__,
            )
            raise CBRUnavailable("Bank of Russia key rate unavailable") from exc

        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise CBRUnavailable("Bank of Russia returned invalid key-rate XML") from exc

        candidates = _parse_key_rate_candidates(root)
        eligible = [item for item in candidates if item[0] <= target]
        if not eligible:
            raise CBRUnavailable("Bank of Russia response has no current key rate")
        effective_date, value = max(eligible, key=lambda item: item[0])
        return CBRKeyRate(
            value=value,
            effective_date=effective_date,
            fetched_at=datetime.now(UTC),
        )

def _parse_key_rate_candidates(root: ET.Element) -> list[tuple[date, str]]:
    candidates = _key_rate_candidates_from_root(root)
    if candidates:
        return candidates

    result = next(
        (
            element
            for element in root.iter()
            if _local_name(element.tag) == "KeyRateXMLResult"
        ),
        None,
    )
    embedded = (result.text or "").strip() if result is not None else ""
    if not embedded.startswith("<"):
        return []
    try:
        embedded_root = ET.fromstring(embedded)
    except ET.ParseError as exc:
        raise CBRUnavailable("Bank of Russia returned invalid embedded key-rate XML") from exc
    return _key_rate_candidates_from_root(embedded_root)


def _key_rate_candidates_from_root(root: ET.Element) -> list[tuple[date, str]]:
    result: list[tuple[date, str]] = []
    for row in root.iter():
        if _local_name(row.tag) != "KR":
            continue
        values = {
            _local_name(child.tag): (child.text or "").strip()
            for child in row
        }
        date_text = values.get("DT", "")
        rate_text = values.get("Rate", "").replace(",", ".")
        try:
            effective_date = datetime.fromisoformat(
                date_text.replace("Z", "+00:00")
            ).date()
            rate = Decimal(rate_text)
        except (InvalidOperation, ValueError) as exc:
            raise CBRUnavailable("Bank of Russia returned invalid key rate") from exc
        if not rate.is_finite() or rate <= 0:
            raise CBRUnavailable("Bank of Russia returned invalid key-rate value")
        result.append((effective_date, format(rate.normalize(), "f")))
    return result


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_effective_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError as exc:
        raise CBRUnavailable("Bank of Russia returned invalid rate date") from exc
