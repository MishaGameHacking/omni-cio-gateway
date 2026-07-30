from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from json import JSONDecodeError
import json
import re
from typing import TypeAlias
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from pydantic import ValidationError

from omni_cio.contracts.v1.market import MarketQuoteV1, MarketSourceV1, SourceAuthority
from omni_cio.contracts.v1.moex import (
    MoexIssQuoteErrorCode,
    MoexIssQuoteStatus,
    MoexIssTqbrQuoteSnapshotV1,
)


MOEX_ISS_TQBR_QUOTE_ENDPOINT_TEMPLATE = (
    "https://iss.moex.com/iss/engines/stock/markets/shares/"
    "boards/TQBR/securities/{secid}.json"
)
MOEX_ISS_QUOTE_PROVIDER = "Moscow Exchange ISS"
MOEX_ISS_TQBR_QUOTE_SOURCE_ID = "ISS.stock.shares.TQBR.marketdata"
DEFAULT_MOEX_ISS_QUOTE_TIMEOUT_SECONDS = 10.0
DEFAULT_MOEX_ISS_QUOTE_MAX_RESPONSE_BYTES = 1_000_000

_SECURITIES_COLUMNS = (
    "SECID",
    "BOARDID",
    "SHORTNAME",
    "LOTSIZE",
    "DECIMALS",
    "CURRENCYID",
)
_MARKETDATA_COLUMNS = (
    "SECID",
    "BOARDID",
    "LAST",
    "BID",
    "OFFER",
    "SYSTIME",
)
_QUERY_PARAMS = {
    "iss.meta": "off",
    "iss.only": "securities,marketdata",
    "securities.columns": ",".join(_SECURITIES_COLUMNS),
    "marketdata.columns": ",".join(_MARKETDATA_COLUMNS),
}
_ALLOWED_CONTENT_TYPES = {
    "application/json",
    "text/json",
}
_SECID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,35}$")
_MOSCOW_TIMEZONE = ZoneInfo("Europe/Moscow")
_MAX_CLOCK_SKEW = timedelta(minutes=5)

JsonObject: TypeAlias = dict[str, object]


class MoexIssQuoteSourceError(ValueError):
    """The official MOEX ISS quote payload cannot be handled safely."""


def _aware_utc(value: datetime | None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise MoexIssQuoteSourceError("MOEX_ISS_QUOTE_TIMESTAMP_MUST_BE_AWARE")
    return result.astimezone(timezone.utc)


def _normalize_secid(value: str) -> str:
    if not isinstance(value, str):
        raise MoexIssQuoteSourceError("MOEX_ISS_QUOTE_SECID_INVALID")
    result = value.strip().upper()
    if not _SECID_PATTERN.fullmatch(result):
        raise MoexIssQuoteSourceError("MOEX_ISS_QUOTE_SECID_INVALID")
    return result


def build_moex_iss_tqbr_quote_url(secid: str) -> str:
    """Build one fixed HTTPS endpoint after strict SECID validation."""
    normalized = _normalize_secid(secid)
    return MOEX_ISS_TQBR_QUOTE_ENDPOINT_TEMPLATE.format(
        secid=quote(normalized, safe=""),
    )


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise MoexIssQuoteSourceError(
                MoexIssQuoteErrorCode.DUPLICATE_CONFLICT.value
            )
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> object:
    raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.JSON_INVALID.value)


def _load_json_object(payload: bytes) -> JsonObject:
    if not isinstance(payload, bytes) or not payload:
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.EMPTY.value)
    try:
        text = payload.decode("utf-8-sig")
        document = json.loads(
            text,
            parse_float=Decimal,
            parse_int=int,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except MoexIssQuoteSourceError:
        raise
    except (UnicodeDecodeError, JSONDecodeError, RecursionError) as exc:
        raise MoexIssQuoteSourceError(
            MoexIssQuoteErrorCode.JSON_INVALID.value
        ) from exc
    if not isinstance(document, dict):
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.SCHEMA_INVALID.value)
    return document


def _table_rows(
    document: JsonObject,
    *,
    name: str,
    expected_columns: tuple[str, ...],
) -> tuple[JsonObject, ...]:
    block = document.get(name)
    if not isinstance(block, dict):
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.SCHEMA_INVALID.value)
    columns = block.get("columns")
    data = block.get("data")
    if (
        not isinstance(columns, list)
        or tuple(columns) != expected_columns
        or not isinstance(data, list)
    ):
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.SCHEMA_INVALID.value)

    rows: list[JsonObject] = []
    for row in data:
        if not isinstance(row, list) or len(row) != len(expected_columns):
            raise MoexIssQuoteSourceError(
                MoexIssQuoteErrorCode.SCHEMA_INVALID.value
            )
        rows.append(dict(zip(expected_columns, row, strict=True)))
    return tuple(rows)


def _single_row(rows: tuple[JsonObject, ...]) -> JsonObject:
    if not rows:
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.EMPTY.value)
    if len(rows) != 1:
        raise MoexIssQuoteSourceError(
            MoexIssQuoteErrorCode.DUPLICATE_CONFLICT.value
        )
    return rows[0]


def _require_identity(row: JsonObject, *, secid: str) -> None:
    if row.get("SECID") != secid or row.get("BOARDID") != "TQBR":
        raise MoexIssQuoteSourceError(
            MoexIssQuoteErrorCode.IDENTITY_MISMATCH.value
        )


def _require_short_name(value: object) -> str:
    if not isinstance(value, str):
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.SCHEMA_INVALID.value)
    result = value.strip()
    if not result or len(result) > 256:
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.SCHEMA_INVALID.value)
    return result


def _require_integer(
    value: object,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.SCHEMA_INVALID.value)
    if value < minimum or value > maximum:
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.SCHEMA_INVALID.value)
    return value


def _normalize_currency(value: object) -> str:
    if not isinstance(value, str):
        raise MoexIssQuoteSourceError(
            MoexIssQuoteErrorCode.CURRENCY_INVALID.value
        )
    normalized = value.strip().upper()
    if normalized in {"RUB", "SUR"}:
        return "RUB"
    raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.CURRENCY_INVALID.value)


def _optional_positive_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.PRICE_INVALID.value)
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, str):
        try:
            result = Decimal(value.strip().replace(",", "."))
        except InvalidOperation as exc:
            raise MoexIssQuoteSourceError(
                MoexIssQuoteErrorCode.PRICE_INVALID.value
            ) from exc
    else:
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.PRICE_INVALID.value)
    if not result.is_finite() or result <= 0:
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.PRICE_INVALID.value)
    return result


def _parse_system_time(value: object, *, retrieved_at: datetime) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise MoexIssQuoteSourceError(
            MoexIssQuoteErrorCode.TIMESTAMP_INVALID.value
        )
    text = value.strip().replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise MoexIssQuoteSourceError(
            MoexIssQuoteErrorCode.TIMESTAMP_INVALID.value
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=_MOSCOW_TIMEZONE)
    result = parsed.astimezone(timezone.utc)
    if result > retrieved_at + _MAX_CLOCK_SKEW:
        raise MoexIssQuoteSourceError(
            MoexIssQuoteErrorCode.TIMESTAMP_INVALID.value
        )
    return result


def parse_moex_iss_tqbr_quote_json(
    payload: bytes,
    *,
    secid: str,
    retrieved_at: datetime | None = None,
) -> MoexIssTqbrQuoteSnapshotV1:
    """Parse one bounded ISS response as data without retaining raw JSON."""
    normalized_secid = _normalize_secid(secid)
    observed_at = _aware_utc(retrieved_at)
    document = _load_json_object(payload)
    securities = _single_row(
        _table_rows(
            document,
            name="securities",
            expected_columns=_SECURITIES_COLUMNS,
        )
    )
    marketdata = _single_row(
        _table_rows(
            document,
            name="marketdata",
            expected_columns=_MARKETDATA_COLUMNS,
        )
    )
    _require_identity(securities, secid=normalized_secid)
    _require_identity(marketdata, secid=normalized_secid)

    short_name = _require_short_name(securities["SHORTNAME"])
    lot_size = _require_integer(
        securities["LOTSIZE"],
        minimum=1,
        maximum=1_000_000_000,
    )
    decimals = _require_integer(
        securities["DECIMALS"],
        minimum=0,
        maximum=12,
    )
    currency = _normalize_currency(securities["CURRENCYID"])
    last_price = _optional_positive_decimal(marketdata["LAST"])
    best_bid = _optional_positive_decimal(marketdata["BID"])
    best_ask = _optional_positive_decimal(marketdata["OFFER"])
    if last_price is None and best_bid is None and best_ask is None:
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.EMPTY.value)
    if best_bid is not None and best_ask is not None and best_bid > best_ask:
        raise MoexIssQuoteSourceError(MoexIssQuoteErrorCode.PRICE_INVALID.value)
    as_of = _parse_system_time(
        marketdata["SYSTIME"],
        retrieved_at=observed_at,
    )
    source = MarketSourceV1(
        provider=MOEX_ISS_QUOTE_PROVIDER,
        authority=SourceAuthority.OFFICIAL,
        retrieved_at=observed_at,
        source_id=MOEX_ISS_TQBR_QUOTE_SOURCE_ID,
    )
    try:
        quote_value = MarketQuoteV1(
            instrument_key=f"MOEX:TQBR:{normalized_secid}",
            currency=currency,
            as_of=as_of,
            source=source,
            last_price=last_price,
            best_bid=best_bid,
            best_ask=best_ask,
        )
    except ValidationError as exc:
        raise MoexIssQuoteSourceError(
            MoexIssQuoteErrorCode.PRICE_INVALID.value
        ) from exc
    return MoexIssTqbrQuoteSnapshotV1(
        secid=normalized_secid,
        retrieved_at=observed_at,
        status=MoexIssQuoteStatus.AVAILABLE,
        source=source,
        quote=quote_value,
        short_name=short_name,
        lot_size=lot_size,
        decimals=decimals,
        warnings=(
            "Public MOEX ISS market data may be delayed and is for informational use.",
        ),
    )


def _unavailable_snapshot(
    *,
    secid: str,
    retrieved_at: datetime,
    error_code: MoexIssQuoteErrorCode,
) -> MoexIssTqbrQuoteSnapshotV1:
    return MoexIssTqbrQuoteSnapshotV1(
        secid=secid,
        retrieved_at=retrieved_at,
        status=MoexIssQuoteStatus.UNAVAILABLE,
        error_code=error_code,
        warnings=("Official MOEX ISS quote is unavailable.",),
    )


def _mapped_error_code(error: MoexIssQuoteSourceError) -> MoexIssQuoteErrorCode:
    try:
        return MoexIssQuoteErrorCode(str(error))
    except ValueError:
        return MoexIssQuoteErrorCode.SCHEMA_INVALID


def _read_bounded_response(
    active_client: httpx.Client,
    *,
    url: str,
    timeout_seconds: float,
    max_response_bytes: int,
) -> tuple[int, str, bytes, bool]:
    with active_client.stream(
        "GET",
        url,
        params=_QUERY_PARAMS,
        headers={
            "Accept": "application/json",
            "User-Agent": "omni-cio-gateway/readonly-moex-iss-quote-v1",
        },
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


def fetch_moex_iss_tqbr_quote(
    *,
    secid: str,
    retrieved_at: datetime | None = None,
    transport: httpx.BaseTransport | None = None,
    timeout_seconds: float = DEFAULT_MOEX_ISS_QUOTE_TIMEOUT_SECONDS,
    max_response_bytes: int = DEFAULT_MOEX_ISS_QUOTE_MAX_RESPONSE_BYTES,
) -> MoexIssTqbrQuoteSnapshotV1:
    """Fetch one TQBR quote from a fixed official ISS endpoint, fail closed."""
    normalized_secid = _normalize_secid(secid)
    observed_at = _aware_utc(retrieved_at)
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not 0.1 <= timeout_seconds <= 30.0
    ):
        raise MoexIssQuoteSourceError("MOEX_ISS_QUOTE_TIMEOUT_INVALID")
    if (
        isinstance(max_response_bytes, bool)
        or not isinstance(max_response_bytes, int)
        or not 1_024 <= max_response_bytes <= 5_000_000
    ):
        raise MoexIssQuoteSourceError("MOEX_ISS_QUOTE_RESPONSE_LIMIT_INVALID")
    url = build_moex_iss_tqbr_quote_url(normalized_secid)

    try:
        with httpx.Client(
            timeout=float(timeout_seconds),
            verify=True,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        ) as client:
            status_code, content_type, payload, too_large = _read_bounded_response(
                client,
                url=url,
                timeout_seconds=float(timeout_seconds),
                max_response_bytes=max_response_bytes,
            )
    except httpx.HTTPError:
        return _unavailable_snapshot(
            secid=normalized_secid,
            retrieved_at=observed_at,
            error_code=MoexIssQuoteErrorCode.NETWORK_ERROR,
        )

    if status_code != 200:
        return _unavailable_snapshot(
            secid=normalized_secid,
            retrieved_at=observed_at,
            error_code=MoexIssQuoteErrorCode.HTTP_ERROR,
        )
    if content_type not in _ALLOWED_CONTENT_TYPES:
        return _unavailable_snapshot(
            secid=normalized_secid,
            retrieved_at=observed_at,
            error_code=MoexIssQuoteErrorCode.CONTENT_TYPE_INVALID,
        )
    if too_large:
        return _unavailable_snapshot(
            secid=normalized_secid,
            retrieved_at=observed_at,
            error_code=MoexIssQuoteErrorCode.RESPONSE_TOO_LARGE,
        )
    try:
        return parse_moex_iss_tqbr_quote_json(
            payload,
            secid=normalized_secid,
            retrieved_at=observed_at,
        )
    except MoexIssQuoteSourceError as exc:
        return _unavailable_snapshot(
            secid=normalized_secid,
            retrieved_at=observed_at,
            error_code=_mapped_error_code(exc),
        )
