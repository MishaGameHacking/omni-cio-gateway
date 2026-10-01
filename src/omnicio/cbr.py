"""Bank of Russia daily USD/RUB reference-rate adapter."""

from __future__ import annotations

import logging
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

_CBR_DAILY_URL = "https://www.cbr.ru/scripts/XML_daily.asp"


class CBRUnavailable(RuntimeError):
    """The Bank of Russia daily-rate feed is unavailable or malformed."""


@dataclass(frozen=True, slots=True)
class CBRRate:
    currency: str
    value: str
    nominal: int
    effective_date: date
    fetched_at: datetime


class CBRClient:
    def __init__(
        self,
        *,
        timeout_seconds: int = 6,
        cache_seconds: int = 3600,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.cache_seconds = cache_seconds
        self._lock = threading.Lock()
        self._cached_usd: CBRRate | None = None
        self._expires_at = 0.0

    def usd_rub_rate(self) -> CBRRate:
        cached = self._cached_usd
        if cached is not None and time.monotonic() < self._expires_at:
            return cached

        with self._lock:
            cached = self._cached_usd
            if cached is not None and time.monotonic() < self._expires_at:
                return cached

            try:
                rate = self._fetch_usd_rub()
            except CBRUnavailable:
                if cached is not None:
                    logger.warning("Bank of Russia rate refresh failed; using cached value")
                    self._expires_at = time.monotonic() + min(self.cache_seconds, 300)
                    return cached
                raise

            self._cached_usd = rate
            self._expires_at = time.monotonic() + self.cache_seconds
            return rate

    def _fetch_usd_rub(self) -> CBRRate:
        request = urllib.request.Request(
            _CBR_DAILY_URL,
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


def _parse_effective_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError as exc:
        raise CBRUnavailable("Bank of Russia returned invalid rate date") from exc
