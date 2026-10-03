"""Minimal read-only Moscow Exchange ISS adapter used by R4 bond screening."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast

MOEX_ISS_ROOT = "https://iss.moex.com/iss"


class MoexError(RuntimeError):
    """MOEX ISS response is unavailable or cannot be used safely."""


@dataclass(frozen=True, slots=True)
class MoexBondSnapshot:
    secid: str
    board_id: str
    yield_percent: Decimal | None
    yield_to_offer_percent: Decimal | None
    call_option_yield_percent: Decimal | None
    ytw_percent: Decimal | None
    duration_days: Decimal | None
    call_option_duration_days: Decimal | None
    accrued_interest_rub: Decimal | None
    value_today_rub: Decimal | None
    volume_today: Decimal | None
    offer_date: str
    maturity_date: str
    source_url: str


@dataclass(frozen=True, slots=True)
class MoexIssClient:
    timeout_seconds: int = 10

    def bond_snapshot(self, secid: str, board_id: str) -> MoexBondSnapshot | None:
        sec = _identifier(secid, "security id")
        board = _identifier(board_id, "board id")
        path = (
            f"{MOEX_ISS_ROOT}/engines/stock/markets/bonds/boards/"
            f"{urllib.parse.quote(board, safe='')}/securities/"
            f"{urllib.parse.quote(sec, safe='')}.json"
        )
        query = urllib.parse.urlencode(
            {
                "iss.meta": "off",
                "iss.only": "securities,marketdata",
                "securities.columns": ",".join(
                    (
                        "SECID",
                        "BOARDID",
                        "MATDATE",
                        "ACCRUEDINT",
                        "DURATION",
                        "CALLOPTIONYIELD",
                        "CALLOPTIONDURATION",
                    )
                ),
                "marketdata.columns": ",".join(
                    (
                        "SECID",
                        "BOARDID",
                        "YIELD",
                        "YIELDTOOFFER",
                        "OFFERDATE",
                        "VALTODAY",
                        "VOLTODAY",
                    )
                ),
            }
        )
        url = f"{path}?{query}"
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "omnicio-r4-evidence/1.0"},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
                context=ssl.create_default_context(),
            ) as response:
                payload_raw = json.loads(response.read().decode("utf-8"))
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            urllib.error.URLError,
        ) as exc:
            raise MoexError("MOEX ISS is unavailable") from exc
        if not isinstance(payload_raw, dict):
            raise MoexError("MOEX ISS returned malformed payload")
        payload = cast(dict[str, object], payload_raw)
        securities = _first_row(payload, "securities")
        marketdata = _first_row(payload, "marketdata")
        if securities is None and marketdata is None:
            return None

        security = securities or {}
        market = marketdata or {}
        returned_secid = str(
            market.get("SECID") or security.get("SECID") or ""
        ).strip()
        returned_board = str(
            market.get("BOARDID") or security.get("BOARDID") or ""
        ).strip()
        if returned_secid != sec or returned_board != board:
            raise MoexError("MOEX ISS returned a different security")

        market_yield = _decimal(market.get("YIELD"))
        offer_yield = _decimal(market.get("YIELDTOOFFER"))
        call_yield = _decimal(security.get("CALLOPTIONYIELD"))
        ytw_values = tuple(
            value
            for value in (market_yield, offer_yield, call_yield)
            if value is not None
        )
        ytw = min(ytw_values) if ytw_values else None

        return MoexBondSnapshot(
            secid=sec,
            board_id=board,
            yield_percent=market_yield,
            yield_to_offer_percent=offer_yield,
            call_option_yield_percent=call_yield,
            ytw_percent=ytw,
            duration_days=_decimal(security.get("DURATION")),
            call_option_duration_days=_decimal(
                security.get("CALLOPTIONDURATION")
            ),
            accrued_interest_rub=_decimal(security.get("ACCRUEDINT")),
            value_today_rub=_decimal(market.get("VALTODAY")),
            volume_today=_decimal(market.get("VOLTODAY")),
            offer_date=str(market.get("OFFERDATE") or ""),
            maturity_date=str(security.get("MATDATE") or ""),
            source_url=url,
        )


def _first_row(
    payload: dict[str, object],
    key: str,
) -> dict[str, object] | None:
    block = payload.get(key)
    if not isinstance(block, dict):
        return None
    data = cast(dict[str, object], block)
    columns_raw = data.get("columns")
    rows_raw = data.get("data")
    if not isinstance(columns_raw, list) or not isinstance(rows_raw, list):
        raise MoexError(f"MOEX ISS {key} block is malformed")
    if not rows_raw:
        return None
    columns = [str(item) for item in columns_raw]
    row = rows_raw[0]
    if not isinstance(row, list) or len(row) != len(columns):
        raise MoexError(f"MOEX ISS {key} row is malformed")
    return dict(zip(columns, cast(list[object], row), strict=True))


def _identifier(value: str, label: str) -> str:
    clean = value.strip().upper()
    if not clean or len(clean) > 32:
        raise ValueError(f"{label} is invalid")
    if not all(char.isalnum() or char in "._-" for char in clean):
        raise ValueError(f"{label} is invalid")
    return clean


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise MoexError("MOEX ISS returned invalid numeric value") from exc
    if not result.is_finite():
        raise MoexError("MOEX ISS returned non-finite numeric value")
    return result
