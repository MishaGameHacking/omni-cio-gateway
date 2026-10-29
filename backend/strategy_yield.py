"""Comparable bond yield, with explicit missing-data failures; no forecasts."""
from datetime import datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
import re

import httpx
from fastapi import HTTPException

try:
    from .volume_contract import decimal, timestamp, text_number
    from . import portfolio_details as details
except ImportError:
    from volume_contract import decimal, timestamp, text_number
    import portfolio_details as details

CBR_URL = "https://www.cbr.ru/hd_base/KeyRate/"


class RateTable(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cells, self.cell, self.inside = [], [], False

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self.cell, self.inside = [], True

    def handle_data(self, data):
        if self.inside:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.inside:
            self.cells.append("".join(self.cell).strip())
            self.inside = False


def parse_key_rate(document: str, now: datetime) -> dict:
    parser = RateTable()
    parser.feed(document)
    observations = []
    for index, cell in enumerate(parser.cells[:-1]):
        if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", cell):
            continue
        day = datetime.strptime(cell, "%d.%m.%Y").date()
        rate = decimal(parser.cells[index + 1].replace(",", "."))
        if day <= now.date() and rate is not None and 0 <= rate <= 100:
            observations.append((day, rate))
    if not observations:
        raise ValueError("key_rate_not_available")
    day, rate = max(observations)
    if (now.date() - day).days > 7:
        raise ValueError("key_rate_observation_stale")
    if len({value for observed, value in observations if observed == day}) != 1:
        raise ValueError("key_rate_conflict")
    return {"percent": text_number(rate), "effective_date": day.isoformat(),
            "observed_at": now.isoformat(), "source_url": CBR_URL}


def key_rate() -> dict:
    def load():
        try:
            with httpx.Client(timeout=15, follow_redirects=False) as client, client.stream("GET", CBR_URL) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 512_000:
                        raise ValueError("key_rate_response_too_large")
            return parse_key_rate(data.decode("utf-8"), datetime.now(timezone.utc))
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, "key_rate_source_unavailable") from None
    return details.cached(("cbr-key-rate-v1",), 3600, load)


def annual_yield(cost: Decimal, cashflows: list[tuple[int, Decimal]]) -> Decimal:
    """ACT/365 annual effective IRR for strictly positive, known cash flows."""
    if cost <= 0 or not cashflows or len(cashflows) > 600:
        raise ValueError("bond_cashflows_invalid")
    if any(type(day) is not int or not 1 <= day <= 3660 or amount <= 0 for day, amount in cashflows):
        raise ValueError("bond_cashflows_invalid")
    # Float is confined to numerical root finding, never cash/lot arithmetic.
    def present(rate):
        return sum(float(amount) / (1 + rate) ** (day / 365) for day, amount in cashflows)
    low, high = -.95, 10.0
    if not present(high) <= float(cost) <= present(low):
        raise ValueError("bond_yield_outside_solver_bounds")
    for _ in range(80):
        middle = (low + high) / 2
        if present(middle) > float(cost):
            low = middle
        else:
            high = middle
    return Decimal(str((low + high) * 50)).quantize(Decimal("0.0001"))


def _coupon_payments(events, now, maturity):
    payments, dates = [], set()
    for row in events:
        date = timestamp(row.get("couponDate")).date()
        if date <= now.date() or date > maturity.date():
            continue
        amount = decimal(row.get("payOneBond"))
        if str((row.get("payOneBond") or {}).get("currency")).upper() != "RUB":
            raise ValueError("bond_coupon_currency_unknown")
        if amount is None or amount <= 0 or row.get("couponType") != "COUPON_TYPE_CONSTANT" or date in dates:
            raise ValueError("bond_future_coupon_unverified")
        dates.add(date)
        payments.append(((date - now.date()).days, amount))
    return payments


def fixed_bond_cashflows(meta: dict, events: list, now: datetime) -> list[tuple[int, Decimal]]:
    if any(meta.get(flag, False) is not False for flag in (
            "floatingCouponFlag", "amortizationFlag", "perpetualFlag", "subordinatedFlag", "indexedNominalFlag")):
        raise ValueError("bond_cashflows_not_fixed")
    if meta.get("callDate") or meta.get("putDate"):
        raise ValueError("bond_offer_yield_to_worst_required")
    maturity = timestamp(meta.get("maturityDate"))
    days = (maturity.date() - now.date()).days
    if str((meta.get("nominal") or {}).get("currency")).upper() != "RUB":
        raise ValueError("bond_nominal_currency_unknown")
    nominal = decimal(meta.get("nominal"))
    if not 1 <= days <= 3660 or nominal is None or nominal <= 0:
        raise ValueError("bond_maturity_or_nominal_unknown")
    payments = _coupon_payments(events, now, maturity)
    frequency = meta.get("couponQuantityPerYear")
    if type(frequency) is not int or frequency < 1 or frequency > 12 or not payments:
        raise ValueError("bond_coupon_schedule_incomplete")
    dates_in_days = sorted(day for day, _ in payments)
    max_gap = 366 / frequency + 35
    if dates_in_days[0] > max_gap or days - dates_in_days[-1] > 7 or any(
            after - before > max_gap for before, after in zip(dates_in_days, dates_in_days[1:])):
        raise ValueError("bond_coupon_schedule_incomplete")
    return payments + [(days, nominal)]


def yield_filter(config: dict, meta: dict, events: list, all_in_per_unit: Decimal,
                 benchmark: dict, now: datetime) -> dict:
    settings = config.get("construction") or {}
    if settings.get("key_rate_mode") != "at_least_key_rate" or meta.get("instrumentType") != "bond":
        return {"passed": True, "applicable": False}
    rate = decimal(benchmark.get("percent"))
    if rate is None or not 0 <= (now - timestamp(benchmark.get("observed_at"))).total_seconds() < 86400:
        raise ValueError("key_rate_observation_stale")
    result = annual_yield(all_in_per_unit, fixed_bond_cashflows(meta, events, now))
    # A large spread is a warning requiring credit investigation, not a bonus.
    spread = result - rate
    return {"passed": 0 <= spread <= 5, "applicable": True,
            "yield_percent": text_number(result), "key_rate": benchmark,
            "spread_percent": text_number(spread), "tax_basis": "before_personal_tax",
            "reason": None if 0 <= spread <= 5 else "bond_yield_below_floor_or_spread_requires_review",
            "guaranteed": False}
