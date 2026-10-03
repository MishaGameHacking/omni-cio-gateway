"""Minimal read-only Moscow Exchange ISS adapter used by R4 bond screening."""

from __future__ import annotations

import http.client
import json
import re
import ssl
import urllib.parse
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, cast

MOEX_ISS_HOST = "iss.moex.com"
MOEX_ISS_ROOT = f"https://{MOEX_ISS_HOST}/iss"
_MOEX_REQUEST_TARGET = re.compile(
    r"/iss/[A-Za-z0-9._~/%-]+(?:\?[A-Za-z0-9._~%=&,+:-]*)?\Z",
    flags=re.ASCII,
)
_MOEX_IDENTIFIER = re.compile(r"[A-Z0-9._-]{1,32}\Z", flags=re.ASCII)
_MOEX_SECURITY_QUERY = re.compile(r"[A-Z0-9._-]{1,64}\Z", flags=re.ASCII)


class MoexError(RuntimeError):
    """MOEX ISS response is unavailable or cannot be used safely."""


@dataclass(frozen=True, slots=True)
class MoexSecurityIdentity:
    secid: str
    isin: str
    issuer_id: str
    issuer_name: str
    issuer_inn: str
    primary_board_id: str
    is_traded: bool
    source_url: str


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
class MoexLiquiditySnapshot:
    secid: str
    board_id: str
    observed_days: int
    average_daily_value_rub: Decimal
    total_value_rub: Decimal
    source_url: str


@dataclass(frozen=True, slots=True)
class MoexIssClient:
    timeout_seconds: int = 10

    def security_identity(
        self,
        query: str,
        *,
        expected_isin: str = "",
    ) -> MoexSecurityIdentity | None:
        clean_query = query.strip().upper()
        if _MOEX_SECURITY_QUERY.fullmatch(clean_query) is None:
            raise ValueError("MOEX security query is invalid")
        url = (
            f"{MOEX_ISS_ROOT}/securities.json?"
            + urllib.parse.urlencode(
                {
                    "iss.meta": "off",
                    "q": clean_query,
                    "limit": "20",
                    "securities.columns": ",".join(
                        (
                            "secid",
                            "isin",
                            "is_traded",
                            "emitent_id",
                            "emitent_title",
                            "emitent_inn",
                            "primary_boardid",
                        )
                    ),
                }
            )
        )
        payload = self._get_payload(url)
        rows = _rows(payload, "securities")
        normalized_isin = expected_isin.strip().upper()
        matches = [
            row
            for row in rows
            if (
                normalized_isin
                and str(row.get("isin") or "").strip().upper() == normalized_isin
            )
            or (
                not normalized_isin
                and str(row.get("secid") or "").strip().upper()
                == clean_query.upper()
            )
        ]
        if not matches:
            return None
        if len(matches) != 1:
            raise MoexError("MOEX ISS security identity is ambiguous")
        row = matches[0]
        secid = str(row.get("secid") or "").strip().upper()
        isin = str(row.get("isin") or "").strip().upper()
        issuer_id = str(row.get("emitent_id") or "").strip()
        issuer_name = str(row.get("emitent_title") or "").strip()
        issuer_inn = str(row.get("emitent_inn") or "").strip()
        board = str(row.get("primary_boardid") or "").strip().upper()
        traded_raw = row.get("is_traded")
        try:
            traded = int(str(traded_raw)) == 1
        except (TypeError, ValueError) as exc:
            raise MoexError("MOEX ISS security identity has invalid trade flag") from exc
        if not secid or not isin or not issuer_id or not issuer_name or not board:
            raise MoexError("MOEX ISS security identity is incomplete")
        return MoexSecurityIdentity(
            secid=secid,
            isin=isin,
            issuer_id=issuer_id,
            issuer_name=issuer_name,
            issuer_inn=issuer_inn,
            primary_board_id=board,
            is_traded=traded,
            source_url=url,
        )

    def bond_liquidity(
        self,
        secid: str,
        board_id: str,
        *,
        from_date: date,
        till_date: date,
    ) -> MoexLiquiditySnapshot | None:
        sec = _identifier(secid, "security id")
        board = _identifier(board_id, "board id")
        if from_date > till_date:
            raise ValueError("MOEX liquidity window is invalid")
        path = (
            f"{MOEX_ISS_ROOT}/history/engines/stock/markets/bonds/boards/"
            f"{urllib.parse.quote(board, safe='')}/securities/"
            f"{urllib.parse.quote(sec, safe='')}.json"
        )
        query = urllib.parse.urlencode(
            {
                "iss.meta": "off",
                "history.columns": "TRADEDATE,SECID,BOARDID,VALUE",
                "from": from_date.isoformat(),
                "till": till_date.isoformat(),
            }
        )
        url = f"{path}?{query}"
        payload = self._get_payload(url)
        rows = _rows(payload, "history")
        values: list[Decimal] = []
        for row in rows:
            returned_secid = str(row.get("SECID") or "").strip()
            returned_board = str(row.get("BOARDID") or "").strip()
            if returned_secid != sec or returned_board != board:
                raise MoexError("MOEX ISS history returned a different security")
            value = _decimal(row.get("VALUE"))
            if value is None or value < 0:
                raise MoexError("MOEX ISS history has invalid traded value")
            values.append(value)
        if not values:
            return None
        total = sum(values, Decimal("0"))
        return MoexLiquiditySnapshot(
            secid=sec,
            board_id=board,
            observed_days=len(values),
            average_daily_value_rub=total / Decimal(len(values)),
            total_value_rub=total,
            source_url=url,
        )

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
        payload = self._get_payload(url)
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


    def _get_payload(self, url: str) -> dict[str, object]:
        target = _moex_request_target(url)
        if _MOEX_REQUEST_TARGET.fullmatch(target) is None:
            raise MoexError("MOEX ISS request target is invalid")
        connection = http.client.HTTPSConnection(
            MOEX_ISS_HOST,
            443,
            timeout=self.timeout_seconds,
            context=ssl.create_default_context(),
        )
        try:
            connection.request(
                "GET",
                target,
                headers={
                    "User-Agent": "omnicio-r4-evidence/1.0",
                    "Accept": "application/json",
                },
            )
            response = connection.getresponse()
            if response.status != 200:
                raise MoexError(
                    f"MOEX ISS returned HTTP {response.status}"
                )
            payload_raw = json.loads(response.read().decode("utf-8"))
        except MoexError:
            raise
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            http.client.HTTPException,
        ) as exc:
            raise MoexError("MOEX ISS is unavailable") from exc
        finally:
            connection.close()
        if not isinstance(payload_raw, dict):
            raise MoexError("MOEX ISS returned malformed payload")
        return cast(dict[str, object], payload_raw)


def _moex_request_target(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.hostname != MOEX_ISS_HOST
        or parts.port not in (None, 443)
        or parts.username is not None
        or parts.password is not None
        or parts.fragment
        or not parts.path.startswith("/iss/")
    ):
        raise MoexError("MOEX ISS URL escaped the fixed provider origin")
    return parts.path + (f"?{parts.query}" if parts.query else "")


def _rows(
    payload: dict[str, object],
    key: str,
) -> tuple[dict[str, object], ...]:
    block = payload.get(key)
    if not isinstance(block, dict):
        return ()
    data = cast(dict[str, object], block)
    columns_raw = data.get("columns")
    rows_raw = data.get("data")
    if not isinstance(columns_raw, list) or not isinstance(rows_raw, list):
        raise MoexError(f"MOEX ISS {key} block is malformed")
    columns = [str(item) for item in columns_raw]
    result: list[dict[str, object]] = []
    for raw in rows_raw:
        if not isinstance(raw, list) or len(raw) != len(columns):
            raise MoexError(f"MOEX ISS {key} row is malformed")
        result.append(
            dict(zip(columns, cast(list[object], raw), strict=True))
        )
    return tuple(result)


def _first_row(
    payload: dict[str, object],
    key: str,
) -> dict[str, object] | None:
    rows = _rows(payload, key)
    return rows[0] if rows else None


def _identifier(value: str, label: str) -> str:
    clean = value.strip().upper()
    if _MOEX_IDENTIFIER.fullmatch(clean) is None:
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
