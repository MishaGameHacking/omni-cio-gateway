import hashlib
import hmac
import json
import logging
import os
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from importlib import metadata
from threading import RLock
from time import monotonic
from typing import Any

# T-Bank SDK reads this variable when configuring TLS verification.
# The SDK uses its embedded certificate bundle; nothing is installed system-wide.
os.environ.setdefault("SSL_TBANK_VERIFY", "True")

import grpc
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.protobuf.json_format import MessageToDict
from t_tech.invest import Client, GetOperationsByCursorRequest, InstrumentIdType


logger = logging.getLogger("omni_cio_gateway")

APP_NAME = "omni-cio-readonly-gateway"
TINVEST_TOKEN = os.environ.get("TINVEST_TOKEN", "").strip()
GATEWAY_API_KEY = os.environ.get("GATEWAY_API_KEY", "").strip()

CAPABILITIES = [
    "connection",
    "portfolio_snapshot",
    "portfolio_snapshot_enriched",
    "portfolio_instrument_enrichment",
    "operations_history",
    "instrument_search",
    "instrument_search_smart",
    "market_snapshot",
    "market_last_price",
    "market_order_book",
    "market_trading_status",
]
INSTRUMENT_CACHE_TTL_SECONDS = 6 * 60 * 60
INSTRUMENT_CACHE_MAX_KEYS = 2000
PORTFOLIO_ENRICHMENT_MAX_REFERENCES = 100

_instrument_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_instrument_cache_lock = RLock()

# Render automatically provides the public HTTPS URL of this web service.
# GPT Actions require an explicit absolute server URL in the OpenAPI schema.
PUBLIC_BASE_URL = os.environ.get(
    "RENDER_EXTERNAL_URL",
    "http://localhost:8000",
).rstrip("/")

app = FastAPI(
    title="Omni-CIO Read-Only Gateway",
    version="3.3.1",
    description=(
        "Private read-only gateway between a Custom GPT and T-Invest API. "
        "It exposes connection, raw and enriched portfolio snapshots, operations history, smart instrument search, and read-only market-data snapshots. "
        "It cannot place, replace, or cancel orders."
    ),
    docs_url=None,
    redoc_url=None,
    servers=[
        {
            "url": PUBLIC_BASE_URL,
            "description": "Public HTTPS endpoint of the private Omni-CIO gateway",
        }
    ],
)

bearer = HTTPBearer(auto_error=False)


def require_gateway_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> None:
    if not GATEWAY_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "GATEWAY_NOT_CONFIGURED"},
        )

    supplied = credentials.credentials if credentials else ""
    if not supplied or not hmac.compare_digest(supplied, GATEWAY_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_GATEWAY_KEY"},
            headers={"WWW-Authenticate": "Bearer"},
        )


def package_version(package_name: str) -> str:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return "not-installed"


def safe_error_message(exc: Exception) -> str:
    message = str(exc) or type(exc).__name__
    for secret in (TINVEST_TOKEN, GATEWAY_API_KEY):
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message[:500]


def json_safe_value(value: Any) -> Any:
    """Recursively convert SDK values to objects that standard JSON can encode."""
    if value is None:
        return None

    # IntEnum is also an int, so Enum must be handled before primitive numbers.
    if isinstance(value, Enum):
        enum_name_value = getattr(value, "name", None)
        if isinstance(enum_name_value, str) and enum_name_value:
            return enum_name_value
        return str(getattr(value, "value", value))

    enum_name_value = getattr(value, "name", None)
    if isinstance(enum_name_value, str) and enum_name_value:
        return enum_name_value

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, Decimal):
        return format(value, "f")

    if isinstance(value, dict):
        return {
            str(key): json_safe_value(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple, set, frozenset)):
        return [json_safe_value(item) for item in value]

    if is_dataclass(value):
        return json_safe_value(asdict(value))

    isoformat_method = getattr(value, "isoformat", None)
    if callable(isoformat_method):
        try:
            return isoformat_method()
        except (TypeError, ValueError):
            pass

    return str(value)


def proto_to_dict(message: Any) -> dict[str, Any]:
    """Convert protobuf/dataclass/dict responses to JSON-compatible dicts."""
    if isinstance(message, dict):
        result = json_safe_value(message)
        if isinstance(result, dict):
            return result

    if hasattr(message, "DESCRIPTOR"):
        result = MessageToDict(
            message,
            preserving_proto_field_name=True,
            use_integers_for_enums=False,
        )
        safe_result = json_safe_value(result)
        if isinstance(safe_result, dict):
            return safe_result

    to_dict = getattr(message, "to_dict", None)
    if callable(to_dict):
        result = json_safe_value(to_dict())
        if isinstance(result, dict):
            return result

    if is_dataclass(message):
        result = json_safe_value(asdict(message))
        if isinstance(result, dict):
            return result

    raise TypeError(
        f"Unsupported SDK response type: {type(message).__module__}."
        f"{type(message).__name__}"
    )


ACCOUNT_STATUS_NAMES = {
    0: "ACCOUNT_STATUS_UNSPECIFIED",
    1: "ACCOUNT_STATUS_NEW",
    2: "ACCOUNT_STATUS_OPEN",
    3: "ACCOUNT_STATUS_CLOSED",
    4: "ACCOUNT_STATUS_ALL",
}

ACCOUNT_TYPE_NAMES = {
    0: "ACCOUNT_TYPE_UNSPECIFIED",
    1: "ACCOUNT_TYPE_TINKOFF",
    2: "ACCOUNT_TYPE_TINKOFF_IIS",
    3: "ACCOUNT_TYPE_INVEST_BOX",
    4: "ACCOUNT_TYPE_INVEST_FUND",
    5: "ACCOUNT_TYPE_DEBIT",
    6: "ACCOUNT_TYPE_SAVING",
    7: "ACCOUNT_TYPE_DFA",
}

ACCESS_LEVEL_NAMES = {
    0: "ACCOUNT_ACCESS_LEVEL_UNSPECIFIED",
    1: "ACCOUNT_ACCESS_LEVEL_FULL_ACCESS",
    2: "ACCOUNT_ACCESS_LEVEL_READ_ONLY",
    3: "ACCOUNT_ACCESS_LEVEL_NO_ACCESS",
}


def mask_account_id(account_id: str) -> str:
    if not account_id:
        return "***"
    return f"***{account_id[-4:]}"


def object_field(obj: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(field_name, default)
    return getattr(obj, field_name, default)


def enum_name(value: Any, mapping: dict[int, str]) -> str:
    """Normalize protobuf enum, Python Enum, integer, or string to a name."""
    if value is None:
        return "UNKNOWN"

    name = getattr(value, "name", None)
    if isinstance(name, str) and name:
        return name

    raw_value = getattr(value, "value", value)

    if isinstance(raw_value, bool):
        return str(raw_value)

    if isinstance(raw_value, int):
        return mapping.get(raw_value, str(raw_value))

    text_value = str(raw_value).strip()
    if text_value.isdigit():
        return mapping.get(int(text_value), text_value)

    # Handles strings such as "AccountStatus.ACCOUNT_STATUS_OPEN".
    return text_value.rsplit(".", 1)[-1]


def response_accounts(accounts_response: Any) -> list[Any]:
    direct_accounts = getattr(accounts_response, "accounts", None)
    if direct_accounts is not None:
        return list(direct_accounts)

    accounts_data = proto_to_dict(accounts_response)
    raw_accounts = accounts_data.get("accounts", [])
    return list(raw_accounts) if raw_accounts else []


def safe_account_view(account: Any) -> dict[str, Any]:
    account_id = str(object_field(account, "id", "") or "")
    return {
        "masked_id": mask_account_id(account_id),
        "name": object_field(account, "name"),
        "type": enum_name(
            object_field(account, "type"),
            ACCOUNT_TYPE_NAMES,
        ),
        "status": enum_name(
            object_field(account, "status"),
            ACCOUNT_STATUS_NAMES,
        ),
        "access_level": enum_name(
            object_field(account, "access_level"),
            ACCESS_LEVEL_NAMES,
        ),
    }



OPERATION_TYPE_NUMBER_TO_NAME = {
    0: "OPERATION_TYPE_UNSPECIFIED",
    1: "OPERATION_TYPE_INPUT",
    2: "OPERATION_TYPE_BOND_TAX",
    3: "OPERATION_TYPE_OUTPUT_SECURITIES",
    4: "OPERATION_TYPE_OVERNIGHT",
    5: "OPERATION_TYPE_TAX",
    6: "OPERATION_TYPE_BOND_REPAYMENT_FULL",
    7: "OPERATION_TYPE_SELL_CARD",
    8: "OPERATION_TYPE_DIVIDEND_TAX",
    9: "OPERATION_TYPE_OUTPUT",
    10: "OPERATION_TYPE_BOND_REPAYMENT",
    11: "OPERATION_TYPE_TAX_CORRECTION",
    12: "OPERATION_TYPE_SERVICE_FEE",
    13: "OPERATION_TYPE_BENEFIT_TAX",
    14: "OPERATION_TYPE_MARGIN_FEE",
    15: "OPERATION_TYPE_BUY",
    16: "OPERATION_TYPE_BUY_CARD",
    17: "OPERATION_TYPE_INPUT_SECURITIES",
    18: "OPERATION_TYPE_SELL_MARGIN",
    19: "OPERATION_TYPE_BROKER_FEE",
    20: "OPERATION_TYPE_BUY_MARGIN",
    21: "OPERATION_TYPE_DIVIDEND",
    22: "OPERATION_TYPE_SELL",
    23: "OPERATION_TYPE_COUPON",
    24: "OPERATION_TYPE_SUCCESS_FEE",
    25: "OPERATION_TYPE_DIVIDEND_TRANSFER",
    43: "OPERATION_TYPE_DIV_EXT",
    44: "OPERATION_TYPE_TAX_CORRECTION_COUPON",
    45: "OPERATION_TYPE_CASH_FEE",
    46: "OPERATION_TYPE_OUT_FEE",
    47: "OPERATION_TYPE_OUT_STAMP_DUTY",
    50: "OPERATION_TYPE_OUTPUT_SWIFT",
    51: "OPERATION_TYPE_INPUT_SWIFT",
    53: "OPERATION_TYPE_OUTPUT_ACQUIRING",
    54: "OPERATION_TYPE_INPUT_ACQUIRING",
    55: "OPERATION_TYPE_OUTPUT_PENALTY",
    56: "OPERATION_TYPE_ADVICE_FEE",
    57: "OPERATION_TYPE_TRANS_IIS_BS",
    58: "OPERATION_TYPE_TRANS_BS_BS",
    59: "OPERATION_TYPE_OUT_MULTI",
    60: "OPERATION_TYPE_INP_MULTI",
    61: "OPERATION_TYPE_OVER_PLACEMENT",
    62: "OPERATION_TYPE_OVER_COM",
    63: "OPERATION_TYPE_OVER_INCOME",
    64: "OPERATION_TYPE_OPTION_EXPIRATION",
    65: "OPERATION_TYPE_FUTURE_EXPIRATION",
    66: "OPERATION_TYPE_OTHER_FEE",
    67: "OPERATION_TYPE_OTHER",
    68: "OPERATION_TYPE_DFA_REDEMPTION",
    69: "OPERATION_TYPE_PRIMARY_ORDER",
    70: "OPERATION_TYPE_FUNDING",
}

OPERATION_STATE_NUMBER_TO_NAME = {
    0: "OPERATION_STATE_UNSPECIFIED",
    1: "OPERATION_STATE_EXECUTED",
    2: "OPERATION_STATE_CANCELED",
    3: "OPERATION_STATE_PROGRESS",
}


def normalized_operation_enum(value: Any, mapping: dict[int, str], default: str) -> str:
    if value is None:
        return default

    if isinstance(value, Enum):
        name = getattr(value, "name", None)
        if isinstance(name, str) and name:
            return name
        value = getattr(value, "value", value)

    name = getattr(value, "name", None)
    if isinstance(name, str) and name:
        return name

    if isinstance(value, int) and not isinstance(value, bool):
        return mapping.get(value, str(value))

    text_value = str(value).strip()
    if text_value.isdigit():
        return mapping.get(int(text_value), text_value)

    return text_value.rsplit(".", 1)[-1] or default


OPERATION_CATEGORY_RULES = {
    "deposit": {
        "OPERATION_TYPE_INPUT",
        "OPERATION_TYPE_INPUT_SWIFT",
        "OPERATION_TYPE_INPUT_ACQUIRING",
        "OPERATION_TYPE_INP_MULTI",
        "OPERATION_TYPE_FUNDING",
    },
    "withdrawal": {
        "OPERATION_TYPE_OUTPUT",
        "OPERATION_TYPE_OUTPUT_SWIFT",
        "OPERATION_TYPE_OUTPUT_ACQUIRING",
        "OPERATION_TYPE_OUT_MULTI",
        "OPERATION_TYPE_OUTPUT_PENALTY",
    },
    "buy": {
        "OPERATION_TYPE_BUY",
        "OPERATION_TYPE_BUY_CARD",
        "OPERATION_TYPE_BUY_MARGIN",
        "OPERATION_TYPE_DELIVERY_BUY",
        "OPERATION_TYPE_PRIMARY_ORDER",
    },
    "sell": {
        "OPERATION_TYPE_SELL",
        "OPERATION_TYPE_SELL_CARD",
        "OPERATION_TYPE_SELL_MARGIN",
        "OPERATION_TYPE_DELIVERY_SELL",
    },
    "dividend": {
        "OPERATION_TYPE_DIVIDEND",
        "OPERATION_TYPE_DIVIDEND_TRANSFER",
        "OPERATION_TYPE_DIV_EXT",
    },
    "coupon": {
        "OPERATION_TYPE_COUPON",
    },
    "redemption": {
        "OPERATION_TYPE_BOND_REPAYMENT",
        "OPERATION_TYPE_BOND_REPAYMENT_FULL",
        "OPERATION_TYPE_DFA_REDEMPTION",
        "OPERATION_TYPE_OPTION_EXPIRATION",
        "OPERATION_TYPE_FUTURE_EXPIRATION",
    },
}


def operation_category(operation_type: str) -> str:
    normalized = str(operation_type or "OPERATION_TYPE_UNSPECIFIED").upper()

    if "TAX" in normalized:
        return "tax"

    fee_markers = (
        "_FEE",
        "BROKER_FEE",
        "SERVICE_FEE",
        "SUCCESS_FEE",
        "MARGIN_FEE",
        "CASH_FEE",
        "OTHER_FEE",
        "ADVICE_FEE",
        "TRACK_MFEE",
        "TRACK_PFEE",
        "OVER_COM",
    )
    if any(marker in normalized for marker in fee_markers):
        return "commission"

    for category, types in OPERATION_CATEGORY_RULES.items():
        if normalized in types:
            return category

    if normalized in {
        "OPERATION_TYPE_INPUT_SECURITIES",
        "OPERATION_TYPE_OUTPUT_SECURITIES",
        "OPERATION_TYPE_TRANS_IIS_BS",
        "OPERATION_TYPE_TRANS_BS_BS",
    }:
        return "security_transfer"

    return "other"


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    if isinstance(value, datetime):
        result = value
    else:
        raw = str(value).strip().replace("Z", "+00:00")
        try:
            result = datetime.fromisoformat(raw)
        except ValueError:
            return None

    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def decimal_from_quotation(value: Any) -> Decimal | None:
    if not isinstance(value, dict):
        return None

    try:
        units = Decimal(str(value.get("units", "0") or "0"))
        nano = Decimal(str(value.get("nano", 0) or 0)) / Decimal("1000000000")
        return units + nano
    except (InvalidOperation, ValueError, TypeError):
        return None


def decimal_string(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.000000001"))
    result = format(normalized, "f").rstrip("0").rstrip(".")
    return result or "0"


def safe_money(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    amount = decimal_from_quotation(value)
    currency = str(value.get("currency", "") or "").upper()
    if amount is None and not currency:
        return None

    result: dict[str, Any] = {}
    if amount is not None:
        result["amount"] = decimal_string(amount)
    if currency:
        result["currency"] = currency
    return result


def safe_quotation(value: Any) -> str | None:
    amount = decimal_from_quotation(value)
    return decimal_string(amount) if amount is not None else None


def operation_fingerprint(operation: dict[str, Any]) -> str:
    fingerprint_fields = {
        "date": operation.get("date"),
        "type": operation.get("type"),
        "state": operation.get("state"),
        "instrument_uid": operation.get("instrument_uid"),
        "position_uid": operation.get("position_uid"),
        "figi": operation.get("figi"),
        "payment": operation.get("payment"),
        "quantity": operation.get("quantity"),
        "quantity_done": operation.get("quantity_done"),
        "name": operation.get("name"),
        "description": operation.get("description"),
    }
    payload = json.dumps(
        json_safe_value(fingerprint_fields),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def safe_operation_item(operation: dict[str, Any]) -> dict[str, Any]:
    operation_type = normalized_operation_enum(
        operation.get("type"),
        OPERATION_TYPE_NUMBER_TO_NAME,
        "OPERATION_TYPE_UNSPECIFIED",
    )
    operation_state = normalized_operation_enum(
        operation.get("state"),
        OPERATION_STATE_NUMBER_TO_NAME,
        "OPERATION_STATE_UNSPECIFIED",
    )
    trades_info = operation.get("trades_info")
    trades = trades_info.get("trades", []) if isinstance(trades_info, dict) else []
    child_operations = operation.get("child_operations", [])

    result: dict[str, Any] = {
        "date": operation.get("date"),
        "type": operation_type,
        "category": operation_category(operation_type),
        "state": operation_state,
        "name": operation.get("name"),
        "description": operation.get("description"),
        "instrument_uid": operation.get("instrument_uid") or None,
        "position_uid": operation.get("position_uid") or None,
        "asset_uid": operation.get("asset_uid") or None,
        "figi": operation.get("figi") or None,
        "instrument_type": operation.get("instrument_type") or None,
        "payment": safe_money(operation.get("payment")),
        "price": safe_money(operation.get("price")),
        "commission": safe_money(operation.get("commission")),
        "accrued_interest": safe_money(operation.get("accrued_int")),
        "quantity": operation.get("quantity"),
        "quantity_done": operation.get("quantity_done"),
        "quantity_rest": operation.get("quantity_rest"),
        "has_parent_operation": bool(operation.get("parent_operation_id")),
        "trade_count": len(trades) if isinstance(trades, list) else 0,
        "child_operation_count": (
            len(child_operations) if isinstance(child_operations, list) else 0
        ),
    }

    # Remove empty technical fields but retain meaningful zeros.
    filtered_result = {
        key: value
        for key, value in result.items()
        if value is not None and value != ""
    }
    safe_result = json_safe_value(filtered_result)
    if not isinstance(safe_result, dict):
        raise TypeError("Operation item could not be converted to a JSON object.")
    return safe_result


def add_summary_amount(
    summary: dict[str, dict[str, dict[str, Decimal]]],
    category: str,
    money: dict[str, Any] | None,
) -> None:
    if not money or "amount" not in money:
        return

    currency = str(money.get("currency", "UNKNOWN") or "UNKNOWN").upper()
    try:
        amount = Decimal(str(money["amount"]))
    except (InvalidOperation, ValueError, TypeError):
        return

    bucket = summary[category][currency]
    bucket["net"] += amount
    if amount >= 0:
        bucket["inflow"] += amount
    else:
        bucket["outflow"] += -amount


def serialize_summary(
    summary: dict[str, dict[str, dict[str, Decimal]]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for category, currencies in summary.items():
        result[category] = {}
        for currency, values in currencies.items():
            result[category][currency] = {
                key: decimal_string(value)
                for key, value in values.items()
            }
    return result


def operation_response_items(response: Any) -> tuple[list[dict[str, Any]], bool, str]:
    data = proto_to_dict(response)
    raw_items = data.get("items", [])
    items = [item for item in raw_items if isinstance(item, dict)]
    return (
        items,
        bool(data.get("has_next", False)),
        str(data.get("next_cursor", "") or ""),
    )


INSTRUMENT_KIND_NUMBER_TO_NAME = {
    0: "INSTRUMENT_TYPE_UNSPECIFIED",
    1: "INSTRUMENT_TYPE_BOND",
    2: "INSTRUMENT_TYPE_SHARE",
    3: "INSTRUMENT_TYPE_CURRENCY",
    4: "INSTRUMENT_TYPE_ETF",
    5: "INSTRUMENT_TYPE_FUTURES",
    6: "INSTRUMENT_TYPE_SP",
    7: "INSTRUMENT_TYPE_OPTION",
    8: "INSTRUMENT_TYPE_CLEARING_CERTIFICATE",
    9: "INSTRUMENT_TYPE_INDEX",
    10: "INSTRUMENT_TYPE_COMMODITY",
    11: "INSTRUMENT_TYPE_DFA",
}

INSTRUMENT_TYPE_FILTERS = {
    "all": None,
    "bond": "INSTRUMENT_TYPE_BOND",
    "share": "INSTRUMENT_TYPE_SHARE",
    "currency": "INSTRUMENT_TYPE_CURRENCY",
    "etf": "INSTRUMENT_TYPE_ETF",
    "futures": "INSTRUMENT_TYPE_FUTURES",
    "sp": "INSTRUMENT_TYPE_SP",
    "option": "INSTRUMENT_TYPE_OPTION",
    "clearing_certificate": "INSTRUMENT_TYPE_CLEARING_CERTIFICATE",
    "index": "INSTRUMENT_TYPE_INDEX",
    "commodity": "INSTRUMENT_TYPE_COMMODITY",
    "dfa": "INSTRUMENT_TYPE_DFA",
}

INSTRUMENT_TYPE_ALIASES = {
    "stock": "INSTRUMENT_TYPE_SHARE",
    "stocks": "INSTRUMENT_TYPE_SHARE",
    "shares": "INSTRUMENT_TYPE_SHARE",
    "акция": "INSTRUMENT_TYPE_SHARE",
    "акции": "INSTRUMENT_TYPE_SHARE",
    "bond": "INSTRUMENT_TYPE_BOND",
    "bonds": "INSTRUMENT_TYPE_BOND",
    "облигация": "INSTRUMENT_TYPE_BOND",
    "облигации": "INSTRUMENT_TYPE_BOND",
    "fund": "INSTRUMENT_TYPE_ETF",
    "funds": "INSTRUMENT_TYPE_ETF",
    "etf": "INSTRUMENT_TYPE_ETF",
    "фонд": "INSTRUMENT_TYPE_ETF",
    "фонды": "INSTRUMENT_TYPE_ETF",
    "currency": "INSTRUMENT_TYPE_CURRENCY",
    "валюта": "INSTRUMENT_TYPE_CURRENCY",
    "future": "INSTRUMENT_TYPE_FUTURES",
    "futures": "INSTRUMENT_TYPE_FUTURES",
    "фьючерс": "INSTRUMENT_TYPE_FUTURES",
    "option": "INSTRUMENT_TYPE_OPTION",
    "опцион": "INSTRUMENT_TYPE_OPTION",
    "index": "INSTRUMENT_TYPE_INDEX",
    "индекс": "INSTRUMENT_TYPE_INDEX",
    "commodity": "INSTRUMENT_TYPE_COMMODITY",
    "товар": "INSTRUMENT_TYPE_COMMODITY",
    "dfa": "INSTRUMENT_TYPE_DFA",
    "цфа": "INSTRUMENT_TYPE_DFA",
}


def normalize_search_text(value: Any) -> str:
    text_value = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(text_value.strip().upper().split())


def compact_search_text(value: Any) -> str:
    return re.sub(r"[\s\-_/.:]+", "", normalize_search_text(value))


def normalized_candidate_kind(instrument: dict[str, Any]) -> str:
    raw_kind = normalized_operation_enum(
        instrument.get("instrument_kind"),
        INSTRUMENT_KIND_NUMBER_TO_NAME,
        "INSTRUMENT_TYPE_UNSPECIFIED",
    )
    normalized_kind = normalize_search_text(raw_kind)
    if normalized_kind in INSTRUMENT_KIND_NUMBER_TO_NAME.values():
        return normalized_kind

    raw_type = str(instrument.get("instrument_type", "") or "").strip().lower()
    return INSTRUMENT_TYPE_ALIASES.get(
        raw_type,
        normalized_kind or "INSTRUMENT_TYPE_UNSPECIFIED",
    )


def safe_instrument_candidate(instrument: dict[str, Any]) -> dict[str, Any]:
    """Return only stable, non-secret fields from InstrumentShort."""
    instrument_kind = normalized_candidate_kind(instrument)

    result: dict[str, Any] = {
        "name": instrument.get("name"),
        "ticker": instrument.get("ticker"),
        "isin": instrument.get("isin"),
        "figi": instrument.get("figi"),
        "class_code": instrument.get("class_code"),
        "instrument_type": instrument.get("instrument_type"),
        "instrument_kind": instrument_kind,
        "uid": instrument.get("uid"),
        "position_uid": instrument.get("position_uid"),
        "lot": instrument.get("lot"),
        "api_trade_available_flag": instrument.get("api_trade_available_flag"),
        "for_iis_flag": instrument.get("for_iis_flag"),
        "for_qual_investor_flag": instrument.get("for_qual_investor_flag"),
        "weekend_flag": instrument.get("weekend_flag"),
        "blocked_tca_flag": instrument.get("blocked_tca_flag"),
        "first_1min_candle_date": instrument.get("first_1min_candle_date"),
        "first_1day_candle_date": instrument.get("first_1day_candle_date"),
    }

    safe_result = json_safe_value(
        {
            key: value
            for key, value in result.items()
            if value is not None and value != ""
        }
    )
    if not isinstance(safe_result, dict):
        raise TypeError("Instrument candidate could not be converted to JSON.")
    return safe_result


def instrument_search_items(response: Any) -> list[dict[str, Any]]:
    data = proto_to_dict(response)
    raw_items = data.get("instruments", [])
    if not isinstance(raw_items, list):
        return []
    return [
        safe_instrument_candidate(item)
        for item in raw_items
        if isinstance(item, dict)
    ]


def instrument_identity(candidate: dict[str, Any]) -> str:
    for field_name in ("uid", "position_uid"):
        value = normalize_search_text(candidate.get(field_name))
        if value:
            return f"{field_name}:{value}"

    figi = normalize_search_text(candidate.get("figi"))
    class_code = normalize_search_text(candidate.get("class_code"))
    if figi:
        return f"figi:{figi}:{class_code}"

    ticker = normalize_search_text(candidate.get("ticker"))
    instrument_kind = normalize_search_text(candidate.get("instrument_kind"))
    name = normalize_search_text(candidate.get("name"))
    return f"fallback:{ticker}:{class_code}:{instrument_kind}:{name}"


def instrument_match(candidate: dict[str, Any], query: str) -> tuple[str, int, bool]:
    normalized_query = normalize_search_text(query)
    compact_query = compact_search_text(query)

    fields = {
        "uid": normalize_search_text(candidate.get("uid")),
        "position_uid": normalize_search_text(candidate.get("position_uid")),
        "figi": normalize_search_text(candidate.get("figi")),
        "isin": normalize_search_text(candidate.get("isin")),
        "ticker": normalize_search_text(candidate.get("ticker")),
        "class_code": normalize_search_text(candidate.get("class_code")),
        "name": normalize_search_text(candidate.get("name")),
    }

    exact_identifier_priorities = (
        ("uid", "exact_uid", 1200),
        ("position_uid", "exact_position_uid", 1190),
        ("figi", "exact_figi", 1180),
        ("isin", "exact_isin", 1170),
    )
    for field_name, match_type, base_score in exact_identifier_priorities:
        if fields[field_name] and normalized_query == fields[field_name]:
            return match_type, base_score, True

    ticker_class = "_".join(
        part for part in (fields["ticker"], fields["class_code"]) if part
    )
    if ticker_class and normalized_query == ticker_class:
        return "exact_ticker_class", 1160, True

    if fields["ticker"] and normalized_query == fields["ticker"]:
        return "exact_ticker", 1150, True

    if fields["name"] and normalized_query == fields["name"]:
        return "exact_name", 1050, True

    if fields["ticker"] and fields["ticker"].startswith(normalized_query):
        return "ticker_prefix", 850, False

    if fields["name"] and fields["name"].startswith(normalized_query):
        return "name_prefix", 760, False

    if fields["ticker"] and normalized_query in fields["ticker"]:
        return "ticker_contains", 680, False

    if fields["name"] and normalized_query in fields["name"]:
        return "name_contains", 620, False

    compact_name = compact_search_text(fields["name"])
    if compact_query and compact_name and compact_query in compact_name:
        return "name_compact_contains", 560, False

    return "related_result", 100, False


def smart_rank_instruments(
    candidates: list[dict[str, Any]],
    query: str,
    instrument_type: str,
    api_trade_available_only: bool,
    exact_only: bool,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    requested_kind = INSTRUMENT_TYPE_FILTERS.get(instrument_type)
    scored: list[dict[str, Any]] = []
    type_filtered_out = 0
    api_filtered_out = 0
    non_exact_filtered_out = 0

    for candidate in candidates:
        candidate_kind = normalized_candidate_kind(candidate)
        if requested_kind and candidate_kind != requested_kind:
            type_filtered_out += 1
            continue

        if api_trade_available_only and not bool(
            candidate.get("api_trade_available_flag", False)
        ):
            api_filtered_out += 1
            continue

        match_type, base_score, exact_match = instrument_match(candidate, query)
        if exact_only and not exact_match:
            non_exact_filtered_out += 1
            continue

        score = base_score
        if bool(candidate.get("api_trade_available_flag", False)):
            score += 30
        if bool(candidate.get("for_iis_flag", False)):
            score += 8
        if not bool(candidate.get("for_qual_investor_flag", False)):
            score += 4
        if candidate.get("lot") not in (None, ""):
            score += 2

        enriched = dict(candidate)
        enriched.update(
            {
                "match_type": match_type,
                "match_score": score,
                "exact_match": exact_match,
            }
        )
        scored.append(enriched)

    scored.sort(
        key=lambda item: (
            -int(item.get("match_score", 0)),
            normalize_search_text(item.get("ticker")),
            normalize_search_text(item.get("class_code")),
            normalize_search_text(item.get("name")),
            normalize_search_text(item.get("uid")),
        )
    )

    deduplicated: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicate_count = 0
    for candidate in scored:
        identity = instrument_identity(candidate)
        if identity in seen:
            duplicate_count += 1
            continue
        seen.add(identity)
        candidate["rank"] = len(deduplicated) + 1
        deduplicated.append(candidate)

    quality = {
        "type_filtered_out": type_filtered_out,
        "api_filtered_out": api_filtered_out,
        "non_exact_filtered_out": non_exact_filtered_out,
        "duplicates_removed": duplicate_count,
        "exact_matches": sum(
            1 for item in deduplicated if bool(item.get("exact_match"))
        ),
    }
    return deduplicated, quality


def instrument_reference_identity(reference: dict[str, Any]) -> str:
    instrument_uid = normalize_search_text(
        reference.get("instrument_uid") or reference.get("uid")
    )
    if instrument_uid:
        return f"uid:{instrument_uid}"

    position_uid = normalize_search_text(reference.get("position_uid"))
    if position_uid:
        return f"position_uid:{position_uid}"

    figi = normalize_search_text(reference.get("figi"))
    if figi:
        return f"figi:{figi}"

    ticker = normalize_search_text(reference.get("ticker"))
    class_code = normalize_search_text(reference.get("class_code"))
    if ticker and class_code:
        return f"ticker_class:{ticker}_{class_code}"

    return ""


def instrument_cache_keys(reference: dict[str, Any]) -> list[str]:
    keys: list[str] = []

    instrument_uid = normalize_search_text(
        reference.get("instrument_uid") or reference.get("uid")
    )
    if instrument_uid:
        keys.append(f"uid:{instrument_uid}")

    position_uid = normalize_search_text(reference.get("position_uid"))
    if position_uid:
        keys.append(f"position_uid:{position_uid}")

    figi = normalize_search_text(reference.get("figi"))
    if figi:
        keys.append(f"figi:{figi}")

    ticker = normalize_search_text(reference.get("ticker"))
    class_code = normalize_search_text(reference.get("class_code"))
    if ticker and class_code:
        keys.append(f"ticker_class:{ticker}_{class_code}")

    return keys


def get_cached_instrument(
    reference: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    now = monotonic()
    with _instrument_cache_lock:
        for key in instrument_cache_keys(reference):
            cached = _instrument_cache.get(key)
            if cached is None:
                continue

            stored_at, metadata_value = cached
            if now - stored_at <= INSTRUMENT_CACHE_TTL_SECONDS:
                return dict(metadata_value), key

            _instrument_cache.pop(key, None)

    return None, None


def cache_instrument_metadata(
    reference: dict[str, Any],
    metadata_value: dict[str, Any],
) -> None:
    keys = list(
        dict.fromkeys(
            instrument_cache_keys(reference)
            + instrument_cache_keys(metadata_value)
        )
    )
    if not keys:
        return

    now = monotonic()
    with _instrument_cache_lock:
        if len(_instrument_cache) + len(keys) > INSTRUMENT_CACHE_MAX_KEYS:
            expired_keys = [
                key
                for key, (stored_at, _) in _instrument_cache.items()
                if now - stored_at > INSTRUMENT_CACHE_TTL_SECONDS
            ]
            for key in expired_keys:
                _instrument_cache.pop(key, None)

        if len(_instrument_cache) + len(keys) > INSTRUMENT_CACHE_MAX_KEYS:
            _instrument_cache.clear()

        safe_copy = dict(metadata_value)
        for key in keys:
            _instrument_cache[key] = (now, safe_copy)


def safe_instrument_metadata(instrument: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": instrument.get("name"),
        "ticker": instrument.get("ticker"),
        "class_code": instrument.get("class_code"),
        "isin": instrument.get("isin"),
        "figi": instrument.get("figi"),
        "uid": instrument.get("uid"),
        "position_uid": instrument.get("position_uid"),
        "asset_uid": instrument.get("asset_uid"),
        "instrument_type": instrument.get("instrument_type"),
        "instrument_kind": normalized_candidate_kind(instrument),
        "lot": instrument.get("lot"),
        "currency": instrument.get("currency"),
        "exchange": instrument.get("exchange"),
        "real_exchange": instrument.get("real_exchange"),
        "country_of_risk": instrument.get("country_of_risk"),
        "country_of_risk_name": instrument.get("country_of_risk_name"),
        "otc_flag": instrument.get("otc_flag"),
        "buy_available_flag": instrument.get("buy_available_flag"),
        "sell_available_flag": instrument.get("sell_available_flag"),
        "api_trade_available_flag": instrument.get(
            "api_trade_available_flag"
        ),
        "for_iis_flag": instrument.get("for_iis_flag"),
        "for_qual_investor_flag": instrument.get(
            "for_qual_investor_flag"
        ),
        "weekend_flag": instrument.get("weekend_flag"),
        "blocked_tca_flag": instrument.get("blocked_tca_flag"),
        "min_price_increment": safe_quotation(
            instrument.get("min_price_increment")
        ),
        "nominal": safe_money(instrument.get("nominal")),
        "accrued_interest": safe_money(instrument.get("aci_value")),
        "first_1min_candle_date": instrument.get(
            "first_1min_candle_date"
        ),
        "first_1day_candle_date": instrument.get(
            "first_1day_candle_date"
        ),
    }

    safe_result = json_safe_value(
        {
            key: value
            for key, value in result.items()
            if value is not None and value != ""
        }
    )
    if not isinstance(safe_result, dict):
        raise TypeError("Instrument metadata could not be converted to JSON.")
    return safe_result


def instrument_metadata_from_response(response: Any) -> dict[str, Any]:
    data = proto_to_dict(response)
    instrument = data.get("instrument")
    if not isinstance(instrument, dict):
        raise TypeError("GetInstrumentBy response does not contain instrument.")
    return safe_instrument_metadata(instrument)


def position_collections(
    portfolio_data: dict[str, Any],
    positions_data: dict[str, Any],
) -> list[tuple[str, list[dict[str, Any]]]]:
    collections: list[tuple[str, list[dict[str, Any]]]] = []
    raw_collections = (
        ("portfolio.positions", portfolio_data.get("positions")),
        (
            "portfolio.virtual_positions",
            portfolio_data.get("virtual_positions"),
        ),
        ("positions.securities", positions_data.get("securities")),
        ("positions.futures", positions_data.get("futures")),
        ("positions.options", positions_data.get("options")),
    )

    for source, raw_items in raw_collections:
        if not isinstance(raw_items, list):
            continue
        collections.append(
            (
                source,
                [item for item in raw_items if isinstance(item, dict)],
            )
        )

    return collections


def position_reference(
    item: dict[str, Any],
    source: str,
    index: int,
) -> dict[str, Any]:
    return {
        "source": source,
        "index": index,
        "instrument_uid": item.get("instrument_uid") or item.get("uid"),
        "position_uid": item.get("position_uid"),
        "figi": item.get("figi"),
        "ticker": item.get("ticker"),
        "class_code": item.get("class_code"),
        "instrument_type": item.get("instrument_type"),
    }


def collect_unique_position_references(
    portfolio_data: dict[str, Any],
    positions_data: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    unique: dict[str, dict[str, Any]] = {}
    occurrence_count = 0
    missing_identifier_count = 0

    for source, items in position_collections(portfolio_data, positions_data):
        for index, item in enumerate(items):
            occurrence_count += 1
            reference = position_reference(item, source, index)
            identity = instrument_reference_identity(reference)
            if not identity:
                missing_identifier_count += 1
                continue

            if identity not in unique:
                reference["identity"] = identity
                reference["occurrences"] = 1
                unique[identity] = reference
            else:
                unique[identity]["occurrences"] = (
                    int(unique[identity].get("occurrences", 1)) + 1
                )

    return list(unique.values()), {
        "position_occurrences": occurrence_count,
        "missing_identifier_occurrences": missing_identifier_count,
    }


def instrument_identity_check(
    reference: dict[str, Any],
    metadata_value: dict[str, Any],
) -> dict[str, Any]:
    checks: dict[str, str] = {}
    match_count = 0
    conflict_count = 0

    comparisons = (
        ("instrument_uid", "uid"),
        ("position_uid", "position_uid"),
        ("figi", "figi"),
    )

    for reference_field, metadata_field in comparisons:
        reference_value = normalize_search_text(
            reference.get(reference_field)
        )
        metadata_item = normalize_search_text(
            metadata_value.get(metadata_field)
        )

        if not reference_value:
            checks[reference_field] = "not_present_in_position"
            continue
        if not metadata_item:
            checks[reference_field] = "not_present_in_reference_data"
            continue
        if reference_value == metadata_item:
            checks[reference_field] = "match"
            match_count += 1
        else:
            checks[reference_field] = "conflict"
            conflict_count += 1

    if conflict_count:
        overall = "FAIL"
    elif match_count:
        overall = "PASS"
    else:
        overall = "WARN"

    return {
        "overall": overall,
        "matches": match_count,
        "conflicts": conflict_count,
        "fields": checks,
    }


def instrument_lookup_plans(
    reference: dict[str, Any],
) -> list[tuple[str, Any, str]]:
    plans: list[tuple[str, Any, str]] = []

    instrument_uid = str(reference.get("instrument_uid") or "").strip()
    if instrument_uid:
        plans.append(
            (
                "INSTRUMENT_ID_TYPE_UID",
                InstrumentIdType.INSTRUMENT_ID_TYPE_UID,
                instrument_uid,
            )
        )

    position_uid = str(reference.get("position_uid") or "").strip()
    if position_uid:
        plans.append(
            (
                "INSTRUMENT_ID_TYPE_POSITION_UID",
                InstrumentIdType.INSTRUMENT_ID_TYPE_POSITION_UID,
                position_uid,
            )
        )

    figi = str(reference.get("figi") or "").strip()
    if figi:
        plans.append(
            (
                "INSTRUMENT_ID_TYPE_FIGI",
                InstrumentIdType.INSTRUMENT_ID_TYPE_FIGI,
                figi,
            )
        )

    return plans


def resolve_instrument_reference(
    client: Client,
    reference: dict[str, Any],
) -> dict[str, Any]:
    cached, cache_key = get_cached_instrument(reference)
    if cached is not None:
        return {
            "status": "resolved",
            "reference": reference,
            "resolution": {
                "source": "memory_cache",
                "cache_hit": True,
                "cache_key": cache_key,
                "api_calls": 0,
            },
            "identity_check": instrument_identity_check(
                reference,
                cached,
            ),
            "instrument": cached,
        }

    attempts: list[dict[str, Any]] = []
    api_calls = 0

    for id_type_name, id_type, identifier in instrument_lookup_plans(
        reference
    ):
        api_calls += 1
        try:
            response = client.instruments.get_instrument_by(
                id_type=id_type,
                id=identifier,
            )
            metadata_value = instrument_metadata_from_response(response)
            cache_instrument_metadata(reference, metadata_value)

            return {
                "status": "resolved",
                "reference": reference,
                "resolution": {
                    "source": "T-Invest GetInstrumentBy",
                    "cache_hit": False,
                    "identifier_type": id_type_name,
                    "identifier": identifier,
                    "api_calls": api_calls,
                    "attempts": attempts,
                },
                "identity_check": instrument_identity_check(
                    reference,
                    metadata_value,
                ),
                "instrument": metadata_value,
            }
        except grpc.RpcError as exc:
            _, payload = grpc_error_payload(exc)
            attempts.append(
                {
                    "identifier_type": id_type_name,
                    "identifier": identifier,
                    "status": "error",
                    "error": payload,
                }
            )
            if payload.get("grpc_code") not in {
                "NOT_FOUND",
                "INVALID_ARGUMENT",
            }:
                break
        except Exception as exc:
            attempts.append(
                {
                    "identifier_type": id_type_name,
                    "identifier": identifier,
                    "status": "error",
                    "error": {
                        "code": "INSTRUMENT_LOOKUP_CLIENT_ERROR",
                        "exception_type": type(exc).__name__,
                        "message": safe_error_message(exc),
                    },
                }
            )
            break

    return {
        "status": "unresolved",
        "reference": reference,
        "resolution": {
            "source": "T-Invest GetInstrumentBy",
            "cache_hit": False,
            "api_calls": api_calls,
            "attempts": attempts,
        },
        "identity_check": {
            "overall": "WARN",
            "matches": 0,
            "conflicts": 0,
            "fields": {},
        },
        "instrument": None,
    }


def resolution_lookup(
    directory: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}

    for entry in directory:
        reference = entry.get("reference")
        if isinstance(reference, dict):
            for key in instrument_cache_keys(reference):
                lookup[key] = entry

        instrument = entry.get("instrument")
        if isinstance(instrument, dict):
            for key in instrument_cache_keys(instrument):
                lookup[key] = entry

    return lookup


def enrich_position_items(
    source: str,
    items: list[dict[str, Any]],
    lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched_items: list[dict[str, Any]] = []

    for index, item in enumerate(items):
        reference = position_reference(item, source, index)
        entry = None
        for key in instrument_cache_keys(reference):
            entry = lookup.get(key)
            if entry is not None:
                break

        enriched_item = dict(item)
        if entry is None:
            enriched_item["enrichment_status"] = "unresolved"
            enriched_item["instrument_metadata"] = None
        else:
            enriched_item["enrichment_status"] = entry.get(
                "status",
                "unresolved",
            )
            enriched_item["instrument_metadata"] = entry.get("instrument")
            enriched_item["identity_check"] = entry.get("identity_check")
            enriched_item["metadata_resolution"] = entry.get("resolution")

        enriched_items.append(enriched_item)

    return enriched_items


def build_enriched_collections(
    portfolio_data: dict[str, Any],
    positions_data: dict[str, Any],
    directory: list[dict[str, Any]],
) -> dict[str, Any]:
    lookup = resolution_lookup(directory)
    collections = {
        source: enrich_position_items(source, items, lookup)
        for source, items in position_collections(
            portfolio_data,
            positions_data,
        )
    }

    return {
        "portfolio_positions": collections.get(
            "portfolio.positions",
            [],
        ),
        "virtual_positions": collections.get(
            "portfolio.virtual_positions",
            [],
        ),
        "balances": {
            "securities": collections.get("positions.securities", []),
            "futures": collections.get("positions.futures", []),
            "options": collections.get("positions.options", []),
        },
    }




def decimal_from_any(value: Any) -> Decimal | None:
    """Convert a JSON-safe number or Quotation-like object to Decimal."""
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, Decimal):
        return value

    if isinstance(value, dict):
        if "amount" in value:
            try:
                return Decimal(str(value.get("amount")))
            except (InvalidOperation, ValueError, TypeError):
                return None
        if "units" in value or "nano" in value:
            quotation_value = decimal_from_quotation(value)
            if quotation_value is not None:
                return quotation_value

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def nonnegative_age_seconds(
    timestamp_value: Any,
    retrieved_at: datetime,
) -> float | None:
    timestamp = parse_datetime(timestamp_value)
    if timestamp is None:
        return None
    return round(max(0.0, (retrieved_at - timestamp).total_seconds()), 3)


def safe_market_order_level(level: Any) -> dict[str, Any] | None:
    if not isinstance(level, dict):
        return None

    price = safe_quotation(level.get("price"))
    quantity = level.get("quantity")
    if price is None:
        return None

    result: dict[str, Any] = {"price": price}
    if quantity is not None and quantity != "":
        result["quantity_lots"] = json_safe_value(quantity)
    return result


def sorted_market_levels(
    raw_levels: Any,
    side: str,
    depth: int,
) -> list[dict[str, Any]]:
    if not isinstance(raw_levels, list):
        return []

    levels = [
        safe_level
        for raw_level in raw_levels
        if (safe_level := safe_market_order_level(raw_level)) is not None
    ]

    reverse = side == "bid"
    levels.sort(
        key=lambda item: decimal_from_any(item.get("price")) or Decimal("0"),
        reverse=reverse,
    )
    return levels[:depth]


def market_spread_metrics(
    best_bid: dict[str, Any] | None,
    best_ask: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not best_bid or not best_ask:
        return None

    bid = decimal_from_any(best_bid.get("price"))
    ask = decimal_from_any(best_ask.get("price"))
    if bid is None or ask is None or ask < bid:
        return None

    spread = ask - bid
    midpoint = (ask + bid) / Decimal("2")
    result: dict[str, Any] = {
        "absolute": decimal_string(spread),
    }
    if midpoint > 0:
        result["percent_of_midpoint"] = decimal_string(
            spread / midpoint * Decimal("100")
        )
    return result


def safe_last_price_response(
    response: Any,
    retrieved_at: datetime,
) -> dict[str, Any]:
    data = proto_to_dict(response)
    raw_prices = data.get("last_prices", [])
    raw_price = (
        raw_prices[0]
        if isinstance(raw_prices, list) and raw_prices
        else None
    )
    if not isinstance(raw_price, dict):
        return {
            "status": "unavailable",
            "reason": "T-Invest returned no last price for this instrument.",
        }

    price_time = raw_price.get("time")
    result: dict[str, Any] = {
        "status": "ok",
        "price": safe_quotation(raw_price.get("price")),
        "time": price_time,
        "age_seconds": nonnegative_age_seconds(price_time, retrieved_at),
        "instrument_uid": raw_price.get("instrument_uid"),
        "figi": raw_price.get("figi"),
        "last_price_type": normalized_operation_enum(
            raw_price.get("last_price_type"),
            {},
            "LAST_PRICE_UNSPECIFIED",
        ),
    }
    return json_safe_value(
        {key: value for key, value in result.items() if value is not None}
    )


def safe_trading_status_response(response: Any) -> dict[str, Any]:
    data = proto_to_dict(response)
    result: dict[str, Any] = {
        "status": "ok",
        "trading_status": normalized_operation_enum(
            data.get("trading_status"),
            {},
            "SECURITY_TRADING_STATUS_UNSPECIFIED",
        ),
        "limit_order_available_flag": data.get(
            "limit_order_available_flag"
        ),
        "market_order_available_flag": data.get(
            "market_order_available_flag"
        ),
        "api_trade_available_flag": data.get("api_trade_available_flag"),
        "instrument_uid": data.get("instrument_uid"),
        "figi": data.get("figi"),
        "bestprice_order_available_flag": data.get(
            "bestprice_order_available_flag"
        ),
        "only_best_price": data.get("only_best_price"),
    }
    return json_safe_value(
        {key: value for key, value in result.items() if value is not None}
    )


def safe_order_book_response(
    response: Any,
    requested_depth: int,
    retrieved_at: datetime,
) -> dict[str, Any]:
    data = proto_to_dict(response)
    bids = sorted_market_levels(data.get("bids"), "bid", requested_depth)
    asks = sorted_market_levels(data.get("asks"), "ask", requested_depth)
    best_bid = bids[0] if bids else None
    best_ask = asks[0] if asks else None
    orderbook_time = data.get("orderbook_ts") or data.get("time")

    result: dict[str, Any] = {
        "status": "ok",
        "requested_depth": requested_depth,
        "returned_bid_levels": len(bids),
        "returned_ask_levels": len(asks),
        "depth": data.get("depth"),
        "instrument_uid": data.get("instrument_uid"),
        "figi": data.get("figi"),
        "time": orderbook_time,
        "age_seconds": nonnegative_age_seconds(
            orderbook_time,
            retrieved_at,
        ),
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": market_spread_metrics(best_bid, best_ask),
        "bids": bids,
        "asks": asks,
        "last_price": safe_quotation(data.get("last_price")),
        "close_price": safe_quotation(data.get("close_price")),
        "limit_up": safe_quotation(data.get("limit_up")),
        "limit_down": safe_quotation(data.get("limit_down")),
        "last_price_time": data.get("last_price_ts"),
        "close_price_time": data.get("close_price_ts"),
    }
    return json_safe_value(
        {key: value for key, value in result.items() if value is not None}
    )


def market_component_error(
    component: str,
    exc: Exception,
) -> dict[str, Any]:
    if isinstance(exc, grpc.RpcError):
        http_status, payload = grpc_error_payload(exc)
        return {
            "status": "error",
            "component": component,
            "http_status": http_status,
            "error": payload,
        }

    return {
        "status": "error",
        "component": component,
        "http_status": 502,
        "error": {
            "code": "MARKET_DATA_COMPONENT_ERROR",
            "exception_type": type(exc).__name__,
            "message": safe_error_message(exc),
        },
    }


def estimated_lot_values(
    metadata_value: dict[str, Any] | None,
    last_price: dict[str, Any],
    order_book: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(metadata_value, dict):
        return None

    lot_raw = metadata_value.get("lot")
    lot = decimal_from_any(lot_raw)
    if lot is None or lot <= 0:
        return None

    instrument_kind = str(
        metadata_value.get("instrument_kind", "") or ""
    ).upper()
    currency = str(metadata_value.get("currency", "") or "").upper()

    prices: dict[str, Decimal] = {}
    last_price_value = decimal_from_any(last_price.get("price"))
    if last_price_value is not None:
        prices["last_price"] = last_price_value

    best_bid = order_book.get("best_bid")
    if isinstance(best_bid, dict):
        bid_value = decimal_from_any(best_bid.get("price"))
        if bid_value is not None:
            prices["best_bid"] = bid_value

    best_ask = order_book.get("best_ask")
    if isinstance(best_ask, dict):
        ask_value = decimal_from_any(best_ask.get("price"))
        if ask_value is not None:
            prices["best_ask"] = ask_value

    if not prices:
        return None

    values: dict[str, Any] = {
        "lot": decimal_string(lot),
        "currency": currency or None,
        "instrument_kind": instrument_kind or None,
        "calculation_basis": None,
        "prices_per_instrument_or_point": {
            key: decimal_string(value) for key, value in prices.items()
        },
    }

    if instrument_kind == "INSTRUMENT_TYPE_BOND":
        nominal_money = metadata_value.get("nominal")
        nominal = decimal_from_any(nominal_money)
        if nominal is None:
            values["calculation_basis"] = (
                "Bond quotation is in percent of nominal; nominal was not "
                "available, so lot values were not calculated."
            )
            return json_safe_value(values)

        accrued_money = metadata_value.get("accrued_interest")
        accrued = decimal_from_any(accrued_money) or Decimal("0")
        clean_values = {
            key: price / Decimal("100") * nominal * lot
            for key, price in prices.items()
        }
        full_values = {
            key: clean_value + accrued * lot
            for key, clean_value in clean_values.items()
        }
        values["calculation_basis"] = (
            "bond_price_percent_of_nominal_times_nominal_times_lot; "
            "full value additionally includes accrued interest"
        )
        values["nominal_per_instrument"] = decimal_string(nominal)
        values["accrued_interest_per_instrument"] = decimal_string(accrued)
        values["estimated_clean_value_per_lot"] = {
            key: decimal_string(value) for key, value in clean_values.items()
        }
        values["estimated_full_value_per_lot"] = {
            key: decimal_string(value) for key, value in full_values.items()
        }
    elif instrument_kind in {
        "INSTRUMENT_TYPE_SHARE",
        "INSTRUMENT_TYPE_ETF",
        "INSTRUMENT_TYPE_CURRENCY",
        "INSTRUMENT_TYPE_SP",
    }:
        values["calculation_basis"] = "price_times_lot"
        values["estimated_value_per_lot"] = {
            key: decimal_string(price * lot)
            for key, price in prices.items()
        }
    else:
        values["calculation_basis"] = (
            "No generic lot-value formula was applied for this instrument type."
        )

    return json_safe_value(
        {key: value for key, value in values.items() if value is not None}
    )

def grpc_error_payload(exc: grpc.RpcError) -> tuple[int, dict[str, Any]]:
    grpc_code = exc.code().name if exc.code() else "UNKNOWN"
    details = exc.details() or "T-Invest request failed"
    tracking_id = None

    try:
        for item in exc.trailing_metadata() or ():
            if item.key.lower() == "x-tracking-id":
                tracking_id = item.value
                break
    except Exception:
        tracking_id = None

    http_map = {
        "INVALID_ARGUMENT": 400,
        "UNAUTHENTICATED": 401,
        "PERMISSION_DENIED": 403,
        "NOT_FOUND": 404,
        "RESOURCE_EXHAUSTED": 429,
        "DEADLINE_EXCEEDED": 504,
        "UNAVAILABLE": 503,
    }

    payload: dict[str, Any] = {
        "code": "TINVEST_GRPC_ERROR",
        "grpc_code": grpc_code,
        "message": details,
    }
    if tracking_id:
        payload["tracking_id"] = tracking_id

    return http_map.get(grpc_code, 502), payload


def ensure_configured() -> None:
    missing = []
    if not TINVEST_TOKEN:
        missing.append("TINVEST_TOKEN")
    if not GATEWAY_API_KEY:
        missing.append("GATEWAY_API_KEY")
    if missing:
        raise HTTPException(
            status_code=503,
            detail={"code": "MISSING_ENVIRONMENT_VARIABLES", "missing": missing},
        )


def get_open_account(client: Client) -> tuple[str, dict[str, Any]]:
    accounts_response = client.users.get_accounts()
    accounts = response_accounts(accounts_response)

    open_accounts = [
        account
        for account in accounts
        if enum_name(
            object_field(account, "status"),
            ACCOUNT_STATUS_NAMES,
        ) == "ACCOUNT_STATUS_OPEN"
    ]

    if not open_accounts:
        safe_accounts = [safe_account_view(account) for account in accounts]
        raise HTTPException(
            status_code=404,
            detail={
                "code": "NO_OPEN_ACCOUNT",
                "accessible_account_count": len(accounts),
                "accounts": safe_accounts,
                "message": (
                    "T-Invest returned accounts, but none was classified as "
                    "ACCOUNT_STATUS_OPEN."
                    if accounts
                    else "T-Invest returned no accounts accessible to this token."
                ),
            },
        )

    if len(open_accounts) > 1:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "MULTIPLE_OPEN_ACCOUNTS",
                "accounts": [
                    safe_account_view(account)
                    for account in open_accounts
                ],
                "message": (
                    "Create a T-Invest token restricted to one account "
                    "or extend the gateway with account aliases."
                ),
            },
        )

    account = open_accounts[0]
    account_id = str(object_field(account, "id", "") or "")
    if not account_id:
        raise HTTPException(
            status_code=502,
            detail={"code": "ACCOUNT_ID_MISSING"},
        )

    return account_id, safe_account_view(account)


@app.get(
    "/",
    operation_id="gatewayRoot",
    summary="Show basic gateway information",
    include_in_schema=False,
)
def root() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": app.version,
        "health": f"{PUBLIC_BASE_URL}/health",
        "openapi": f"{PUBLIC_BASE_URL}/openapi.json",
        "capabilities": CAPABILITIES,
        "trading_methods": False,
    }


@app.get(
    "/health",
    operation_id="gatewayHealth",
    summary="Check whether the gateway process is running",
)
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": app.version,
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "tls_mode": "T-Bank SDK embedded certificate",
        "python_version": sys.version.split()[0],
        "sdk_version": package_version("t-tech-investments"),
        "protobuf_version": package_version("protobuf"),
        "grpcio_version": package_version("grpcio"),
        "configured": {
            "tinvest_token": bool(TINVEST_TOKEN),
            "gateway_api_key": bool(GATEWAY_API_KEY),
        },
        "capabilities": CAPABILITIES,
        "trading_methods": False,
    }


@app.get(
    "/connection",
    operation_id="getConnection",
    summary="Verify the T-Invest token and return the masked open account",
    dependencies=[Depends(require_gateway_key)],
)
def connection() -> dict[str, Any]:
    ensure_configured()
    try:
        with Client(TINVEST_TOKEN) as client:
            _, safe_account = get_open_account(client)
            return {
                "status": "connected",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "account": safe_account,
            }
    except HTTPException:
        raise
    except grpc.RpcError as exc:
        http_status, payload = grpc_error_payload(exc)
        raise HTTPException(status_code=http_status, detail=payload) from exc
    except Exception as exc:
        safe_message = safe_error_message(exc)
        logger.exception(
            "Gateway SDK/client failure: %s: %s",
            type(exc).__name__,
            safe_message,
        )
        error_code = (
            "GATEWAY_SDK_COMPATIBILITY_ERROR"
            if isinstance(exc, (AttributeError, TypeError))
            else "GATEWAY_CLIENT_ERROR"
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": error_code,
                "exception_type": type(exc).__name__,
                "message": safe_message,
                "runtime": {
                    "python": sys.version.split()[0],
                    "t_tech_investments": package_version("t-tech-investments"),
                    "protobuf": package_version("protobuf"),
                    "grpcio": package_version("grpcio"),
                },
            },
        ) from exc


@app.get(
    "/snapshot",
    operation_id="getPortfolioSnapshot",
    summary="Get a current read-only portfolio snapshot",
    dependencies=[Depends(require_gateway_key)],
)
def snapshot() -> dict[str, Any]:
    ensure_configured()
    try:
        with Client(TINVEST_TOKEN) as client:
            account_id, safe_account = get_open_account(client)

            portfolio = client.operations.get_portfolio(
                account_id=account_id,
            )
            positions = client.operations.get_positions(account_id=account_id)
            withdraw_limits = client.operations.get_withdraw_limits(
                account_id=account_id
            )

            return {
                "status": "ok",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "account": safe_account,
                "portfolio": proto_to_dict(portfolio),
                "positions": proto_to_dict(positions),
                "withdraw_limits": proto_to_dict(withdraw_limits),
                "warnings": [
                    "withdraw_limits is not automatically equal to money available for a purchase",
                    "market values can change after this snapshot",
                ],
            }
    except HTTPException:
        raise
    except grpc.RpcError as exc:
        http_status, payload = grpc_error_payload(exc)
        raise HTTPException(status_code=http_status, detail=payload) from exc
    except Exception as exc:
        safe_message = safe_error_message(exc)
        logger.exception(
            "Gateway SDK/client failure: %s: %s",
            type(exc).__name__,
            safe_message,
        )
        error_code = (
            "GATEWAY_SDK_COMPATIBILITY_ERROR"
            if isinstance(exc, (AttributeError, TypeError))
            else "GATEWAY_CLIENT_ERROR"
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": error_code,
                "exception_type": type(exc).__name__,
                "message": safe_message,
                "runtime": {
                    "python": sys.version.split()[0],
                    "t_tech_investments": package_version("t-tech-investments"),
                    "protobuf": package_version("protobuf"),
                    "grpcio": package_version("grpcio"),
                },
            },
        ) from exc



@app.get(
    "/snapshot/enriched",
    operation_id="getEnrichedPortfolioSnapshot",
    summary=(
        "Get a read-only portfolio snapshot enriched with exact instrument "
        "reference metadata"
    ),
    dependencies=[Depends(require_gateway_key)],
)
def enriched_snapshot() -> dict[str, Any]:
    ensure_configured()
    retrieved_at = datetime.now(timezone.utc)

    try:
        with Client(TINVEST_TOKEN) as client:
            account_id, safe_account = get_open_account(client)

            portfolio_response = client.operations.get_portfolio(
                account_id=account_id,
            )
            positions_response = client.operations.get_positions(
                account_id=account_id
            )
            withdraw_limits_response = client.operations.get_withdraw_limits(
                account_id=account_id
            )

            portfolio_data = proto_to_dict(portfolio_response)
            positions_data = proto_to_dict(positions_response)
            withdraw_limits_data = proto_to_dict(withdraw_limits_response)

            references, reference_quality = (
                collect_unique_position_references(
                    portfolio_data,
                    positions_data,
                )
            )

            references_to_resolve = references[
                :PORTFOLIO_ENRICHMENT_MAX_REFERENCES
            ]
            skipped_references = references[
                PORTFOLIO_ENRICHMENT_MAX_REFERENCES:
            ]

            directory = [
                resolve_instrument_reference(client, reference)
                for reference in references_to_resolve
            ]
            for reference in skipped_references:
                directory.append(
                    {
                        "status": "unresolved",
                        "reference": reference,
                        "resolution": {
                            "source": "gateway_limit",
                            "cache_hit": False,
                            "api_calls": 0,
                            "error": {
                                "code": "ENRICHMENT_REFERENCE_LIMIT",
                                "message": (
                                    "Reference was not enriched because the "
                                    "per-request safety limit was reached."
                                ),
                            },
                        },
                        "identity_check": {
                            "overall": "WARN",
                            "matches": 0,
                            "conflicts": 0,
                            "fields": {},
                        },
                        "instrument": None,
                    }
                )

            enriched = build_enriched_collections(
                portfolio_data,
                positions_data,
                directory,
            )

            resolved_entries = [
                entry
                for entry in directory
                if entry.get("status") == "resolved"
            ]
            unresolved_entries = [
                entry
                for entry in directory
                if entry.get("status") != "resolved"
            ]
            cache_hits = sum(
                1
                for entry in resolved_entries
                if bool(
                    object_field(
                        entry.get("resolution", {}),
                        "cache_hit",
                        False,
                    )
                )
            )
            api_calls = sum(
                int(
                    object_field(
                        entry.get("resolution", {}),
                        "api_calls",
                        0,
                    )
                    or 0
                )
                for entry in directory
            )
            identity_conflicts = sum(
                1
                for entry in resolved_entries
                if object_field(
                    entry.get("identity_check", {}),
                    "overall",
                )
                == "FAIL"
            )

            warnings = [
                (
                    "Instrument metadata is reference data obtained through "
                    "GetInstrumentBy and is attached without replacing the "
                    "portfolio quantities, prices, balances, or yields."
                ),
                (
                    "api_trade_available_flag, buy_available_flag, and "
                    "sell_available_flag do not prove current market "
                    "liquidity or an executable price."
                ),
                (
                    "Instrument UID is the primary trading-instrument "
                    "identifier; position_uid identifies the portfolio "
                    "position and is also used as a fallback lookup key."
                ),
                (
                    "The in-process metadata cache expires after six hours "
                    "and is cleared whenever Render restarts the service."
                ),
                (
                    "The gateway remains read-only and exposes no order "
                    "placement, replacement, or cancellation endpoints."
                ),
            ]
            if skipped_references:
                warnings.append(
                    (
                        f"Enrichment was limited to "
                        f"{PORTFOLIO_ENRICHMENT_MAX_REFERENCES} unique "
                        "instrument references in this request."
                    )
                )
            if identity_conflicts:
                warnings.append(
                    (
                        f"{identity_conflicts} resolved instrument entries "
                        "contained identifier conflicts. Treat those entries "
                        "as a data-quality warning."
                    )
                )

            return {
                "status": "ok",
                "version": app.version,
                "retrieved_at": retrieved_at.isoformat(),
                "account": safe_account,
                "portfolio": portfolio_data,
                "positions": positions_data,
                "withdraw_limits": withdraw_limits_data,
                "enriched_portfolio_positions": enriched[
                    "portfolio_positions"
                ],
                "enriched_virtual_positions": enriched[
                    "virtual_positions"
                ],
                "enriched_balances": enriched["balances"],
                "instrument_directory": directory,
                "enrichment_quality": {
                    **reference_quality,
                    "unique_instrument_references": len(references),
                    "references_resolved": len(resolved_entries),
                    "references_unresolved": len(unresolved_entries),
                    "references_skipped_by_limit": len(skipped_references),
                    "cache_hits": cache_hits,
                    "instrument_api_calls": api_calls,
                    "identity_conflicts": identity_conflicts,
                    "reference_limit": (
                        PORTFOLIO_ENRICHMENT_MAX_REFERENCES
                    ),
                    "cache_ttl_seconds": (
                        INSTRUMENT_CACHE_TTL_SECONDS
                    ),
                },
                "warnings": warnings,
            }
    except HTTPException:
        raise
    except grpc.RpcError as exc:
        http_status, payload = grpc_error_payload(exc)
        raise HTTPException(status_code=http_status, detail=payload) from exc
    except Exception as exc:
        safe_message = safe_error_message(exc)
        logger.exception(
            "Gateway enriched-snapshot failure: %s: %s",
            type(exc).__name__,
            safe_message,
        )
        error_code = (
            "GATEWAY_SDK_COMPATIBILITY_ERROR"
            if isinstance(exc, (AttributeError, TypeError))
            else "GATEWAY_ENRICHED_SNAPSHOT_ERROR"
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": error_code,
                "exception_type": type(exc).__name__,
                "message": safe_message,
                "runtime": {
                    "python": sys.version.split()[0],
                    "t_tech_investments": package_version(
                        "t-tech-investments"
                    ),
                    "protobuf": package_version("protobuf"),
                    "grpcio": package_version("grpcio"),
                },
            },
        ) from exc




@app.get(
    "/instruments/search",
    operation_id="findInstrument",
    summary="Find instruments by ticker, ISIN, FIGI, UID, position UID, or name",
    dependencies=[Depends(require_gateway_key)],
)
def find_instrument(
    query: str = Query(
        ...,
        min_length=1,
        max_length=120,
        description=(
            "Search text. T-Invest searches by position UID, UID, FIGI, ISIN, "
            "ticker, and name."
        ),
    ),
    limit: int = Query(
        10,
        ge=1,
        le=20,
        description="Maximum number of smart-ranked candidates returned.",
    ),
    instrument_type: str = Query(
        "all",
        description=(
            "Optional local filter: all, share, bond, etf, currency, futures, "
            "option, sp, clearing_certificate, index, commodity, or dfa."
        ),
    ),
    api_trade_available_only: bool = Query(
        False,
        description="Return only instruments marked available for trading through API.",
    ),
    exact_only: bool = Query(
        False,
        description=(
            "Return only exact matches by UID, position UID, FIGI, ISIN, "
            "ticker plus class code, ticker, or full name."
        ),
    ),
) -> dict[str, Any]:
    ensure_configured()
    normalized_query = query.strip()
    if not normalized_query:
        raise HTTPException(
            status_code=422,
            detail={"code": "EMPTY_INSTRUMENT_QUERY"},
        )

    normalized_type = instrument_type.strip().lower()
    if normalized_type not in INSTRUMENT_TYPE_FILTERS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_INSTRUMENT_TYPE_FILTER",
                "allowed": sorted(INSTRUMENT_TYPE_FILTERS),
            },
        )

    try:
        with Client(TINVEST_TOKEN) as client:
            response = client.instruments.find_instrument(query=normalized_query)
            raw_candidates = instrument_search_items(response)
            ranked_candidates, quality = smart_rank_instruments(
                candidates=raw_candidates,
                query=normalized_query,
                instrument_type=normalized_type,
                api_trade_available_only=api_trade_available_only,
                exact_only=exact_only,
            )
            returned = ranked_candidates[:limit]
            best_match = returned[0] if returned else None

            return {
                "status": "ok",
                "search_mode": "smart_ranked_v3_1",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "query": normalized_query,
                "filters": {
                    "instrument_type": normalized_type,
                    "api_trade_available_only": api_trade_available_only,
                    "exact_only": exact_only,
                },
                "raw_candidates": len(raw_candidates),
                "deduplicated_candidates": len(ranked_candidates),
                "returned_candidates": len(returned),
                "truncated": len(ranked_candidates) > limit,
                "quality": quality,
                "best_match": best_match,
                "instruments": returned,
                "warnings": [
                    "Search results are reference data, not a recommendation to buy or sell.",
                    "api_trade_available_flag does not prove current trading status, liquidity, or executable price.",
                    "UID is the preferred trading-instrument identifier; ticker may require class_code for disambiguation.",
                    "The gateway remains read-only and exposes no order placement endpoints.",
                ],
            }
    except HTTPException:
        raise
    except grpc.RpcError as exc:
        http_status, payload = grpc_error_payload(exc)
        raise HTTPException(status_code=http_status, detail=payload) from exc
    except Exception as exc:
        safe_message = safe_error_message(exc)
        logger.exception(
            "Gateway instrument-search failure: %s: %s",
            type(exc).__name__,
            safe_message,
        )
        error_code = (
            "GATEWAY_SDK_COMPATIBILITY_ERROR"
            if isinstance(exc, (AttributeError, TypeError))
            else "GATEWAY_INSTRUMENT_SEARCH_ERROR"
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": error_code,
                "exception_type": type(exc).__name__,
                "message": safe_message,
                "runtime": {
                    "python": sys.version.split()[0],
                    "t_tech_investments": package_version("t-tech-investments"),
                    "protobuf": package_version("protobuf"),
                    "grpcio": package_version("grpcio"),
                },
            },
        ) from exc



@app.get(
    "/market/snapshot",
    operation_id="getMarketSnapshot",
    summary=(
        "Get a current read-only market snapshot for one exact instrument UID"
    ),
    dependencies=[Depends(require_gateway_key)],
)
def market_snapshot(
    instrument_uid: str = Query(
        ...,
        min_length=1,
        max_length=120,
        description=(
            "Exact T-Invest instrument UID. Resolve it with findInstrument or "
            "getEnrichedPortfolioSnapshot before calling this method."
        ),
    ),
    depth: int = Query(
        10,
        ge=1,
        le=20,
        description="Order-book depth returned for bids and asks.",
    ),
) -> dict[str, Any]:
    ensure_configured()
    normalized_uid = instrument_uid.strip()
    if not normalized_uid:
        raise HTTPException(
            status_code=422,
            detail={"code": "EMPTY_INSTRUMENT_UID"},
        )

    retrieved_at = datetime.now(timezone.utc)

    try:
        with Client(TINVEST_TOKEN) as client:
            reference = {"instrument_uid": normalized_uid}
            reference_result = resolve_instrument_reference(
                client,
                reference,
            )
            metadata_value = reference_result.get("instrument")

            try:
                last_price_response = client.market_data.get_last_prices(
                    instrument_id=[normalized_uid]
                )
                last_price = safe_last_price_response(
                    last_price_response,
                    retrieved_at,
                )
            except Exception as exc:
                last_price = market_component_error("last_price", exc)

            try:
                trading_status_response = (
                    client.market_data.get_trading_status(
                        instrument_id=normalized_uid
                    )
                )
                trading_status = safe_trading_status_response(
                    trading_status_response
                )
            except Exception as exc:
                trading_status = market_component_error(
                    "trading_status",
                    exc,
                )

            try:
                order_book_response = client.market_data.get_order_book(
                    instrument_id=normalized_uid,
                    depth=depth,
                )
                order_book = safe_order_book_response(
                    order_book_response,
                    depth,
                    retrieved_at,
                )
            except Exception as exc:
                order_book = market_component_error("order_book", exc)

            components = {
                "instrument_reference": (
                    "ok"
                    if reference_result.get("status") == "resolved"
                    else "error"
                ),
                "last_price": last_price.get("status"),
                "trading_status": trading_status.get("status"),
                "order_book": order_book.get("status"),
            }
            successful_components = sum(
                1 for value in components.values() if value == "ok"
            )
            overall_status = (
                "ok"
                if successful_components == len(components)
                else "partial"
                if successful_components > 0
                else "error"
            )

            lot_values = estimated_lot_values(
                metadata_value if isinstance(metadata_value, dict) else None,
                last_price,
                order_book,
            )

            warnings = [
                (
                    "Last price is the price of the latest recorded trade and "
                    "is not automatically an executable buy or sell price."
                ),
                (
                    "Best ask is the nearest visible sell quote and best bid "
                    "is the nearest visible buy quote at the snapshot time; "
                    "both may change before an order is submitted."
                ),
                (
                    "Order-book quantities are expressed in lots. Prices are "
                    "per instrument, except bond quotations which are expressed "
                    "as a percentage of nominal."
                ),
                (
                    "Trading-status flags describe API availability at the "
                    "retrieval time and do not guarantee sufficient liquidity."
                ),
                (
                    "The gateway remains read-only and exposes no order "
                    "placement, replacement, or cancellation endpoints."
                ),
            ]

            return {
                "status": overall_status,
                "version": app.version,
                "retrieved_at": retrieved_at.isoformat(),
                "instrument_uid": normalized_uid,
                "components": components,
                "instrument_reference": reference_result,
                "last_price": last_price,
                "trading_status": trading_status,
                "order_book": order_book,
                "estimated_lot_values": lot_values,
                "warnings": warnings,
            }
    except HTTPException:
        raise
    except grpc.RpcError as exc:
        http_status, payload = grpc_error_payload(exc)
        raise HTTPException(status_code=http_status, detail=payload) from exc
    except Exception as exc:
        safe_message = safe_error_message(exc)
        logger.exception(
            "Gateway market-snapshot failure: %s: %s",
            type(exc).__name__,
            safe_message,
        )
        error_code = (
            "GATEWAY_SDK_COMPATIBILITY_ERROR"
            if isinstance(exc, (AttributeError, TypeError))
            else "GATEWAY_MARKET_SNAPSHOT_ERROR"
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": error_code,
                "exception_type": type(exc).__name__,
                "message": safe_message,
                "runtime": {
                    "python": sys.version.split()[0],
                    "t_tech_investments": package_version(
                        "t-tech-investments"
                    ),
                    "protobuf": package_version("protobuf"),
                    "grpcio": package_version("grpcio"),
                },
            },
        ) from exc

@app.get(
    "/operations",
    operation_id="getOperationsHistory",
    summary="Get a deduplicated read-only operations history for the selected account",
    dependencies=[Depends(require_gateway_key)],
)
def operations_history(
    days: int = Query(
        90,
        ge=1,
        le=3650,
        description="Number of calendar days to return; default is 90.",
    ),
) -> dict[str, Any]:
    ensure_configured()
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)

    try:
        with Client(TINVEST_TOKEN) as client:
            account_id, safe_account = get_open_account(client)

            cursor = ""
            pages_loaded = 0
            max_pages = 20
            page_limit = 1000
            all_items: list[dict[str, Any]] = []
            has_more = False

            while pages_loaded < max_pages:
                request = GetOperationsByCursorRequest(
                    account_id=account_id,
                    cursor=cursor,
                    limit=page_limit,
                    without_commissions=False,
                    without_trades=False,
                    without_overnights=True,
                )
                response = client.operations.get_operations_by_cursor(request)
                page_items, has_next, next_cursor = operation_response_items(response)
                pages_loaded += 1
                all_items.extend(page_items)

                if not has_next or not next_cursor:
                    has_more = False
                    break

                has_more = True
                if next_cursor == cursor:
                    raise RuntimeError("Operations cursor did not advance.")
                cursor = next_cursor

            filtered_items: list[dict[str, Any]] = []
            seen: set[str] = set()
            duplicates_removed = 0
            outside_period = 0

            for raw_operation in all_items:
                operation_date = parse_datetime(raw_operation.get("date"))
                if operation_date is not None and operation_date < start_time:
                    outside_period += 1
                    continue
                if operation_date is not None and operation_date > end_time:
                    outside_period += 1
                    continue

                fingerprint = operation_fingerprint(raw_operation)
                if fingerprint in seen:
                    duplicates_removed += 1
                    continue
                seen.add(fingerprint)
                filtered_items.append(safe_operation_item(raw_operation))

            filtered_items.sort(
                key=lambda item: str(item.get("date", "")),
                reverse=True,
            )

            executed_summary = defaultdict(
                lambda: defaultdict(
                    lambda: {
                        "net": Decimal("0"),
                        "inflow": Decimal("0"),
                        "outflow": Decimal("0"),
                    }
                )
            )
            state_counts: dict[str, int] = defaultdict(int)
            category_counts: dict[str, int] = defaultdict(int)

            for item in filtered_items:
                state_name = str(item.get("state", "UNKNOWN") or "UNKNOWN")
                category_name = str(item.get("category", "other") or "other")
                state_counts[state_name] += 1
                category_counts[category_name] += 1

                # Only executed operations affect the financial summary.
                if state_name == "OPERATION_STATE_EXECUTED":
                    add_summary_amount(
                        executed_summary,
                        category_name,
                        item.get("payment"),
                    )

            warnings = [
                "Financial totals include only OPERATION_STATE_EXECUTED operations.",
                "Commission operations are included as separate operations and are not added again from nested commission fields.",
                "Operation IDs are omitted because T-Invest states that operation IDs can change over time.",
                "For corporate actions, API history can be incomplete; use the official broker report for exact reconciliation.",
                "Quantity in the operations service is the number of instrument units, not lots.",
            ]
            if has_more:
                warnings.append(
                    f"History was truncated after {max_pages} pages of {page_limit} operations."
                )

            return {
                "status": "ok",
                "retrieved_at": end_time.isoformat(),
                "period": {
                    "from": start_time.isoformat(),
                    "to": end_time.isoformat(),
                    "days": days,
                },
                "account": safe_account,
                "pagination": {
                    "pages_loaded": pages_loaded,
                    "page_limit": page_limit,
                    "truncated": has_more,
                },
                "quality": {
                    "raw_items_loaded": len(all_items),
                    "items_outside_period": outside_period,
                    "duplicates_removed": duplicates_removed,
                    "returned_items": len(filtered_items),
                },
                "state_counts": dict(state_counts),
                "category_counts": dict(category_counts),
                "executed_cash_summary": serialize_summary(executed_summary),
                "operations": filtered_items,
                "warnings": warnings,
            }
    except HTTPException:
        raise
    except grpc.RpcError as exc:
        http_status, payload = grpc_error_payload(exc)
        raise HTTPException(status_code=http_status, detail=payload) from exc
    except Exception as exc:
        safe_message = safe_error_message(exc)
        logger.exception(
            "Gateway operations-history failure: %s: %s",
            type(exc).__name__,
            safe_message,
        )
        error_code = (
            "GATEWAY_SDK_COMPATIBILITY_ERROR"
            if isinstance(exc, (AttributeError, TypeError))
            else "GATEWAY_OPERATIONS_ERROR"
        )
        raise HTTPException(
            status_code=502,
            detail={
                "code": error_code,
                "exception_type": type(exc).__name__,
                "message": safe_message,
                "runtime": {
                    "python": sys.version.split()[0],
                    "t_tech_investments": package_version("t-tech-investments"),
                    "protobuf": package_version("protobuf"),
                    "grpcio": package_version("grpcio"),
                },
            },
        ) from exc


# ---------------------------------------------------------------------------
# GPT Actions-compatible OpenAPI response schemas.
#
# FastAPI represents a return annotation of dict[str, Any] as:
#   {"type": "object", "additionalProperties": true}
# The GPT Actions editor expects object responses to declare `properties`.
# This override changes documentation only; runtime response bodies are not
# filtered or modified.
# ---------------------------------------------------------------------------

def _oa_obj(properties: dict[str, Any], *, required: list[str] | None = None, description: str | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": True,
    }
    if required:
        schema["required"] = required
    if description:
        schema["description"] = description
    return schema


def _oa_array(items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "array", "items": items}


_OA_STRING = {"type": "string"}
_OA_BOOL = {"type": "boolean"}
_OA_INT = {"type": "integer"}
_OA_NUMBER = {"type": "number"}

_OA_MONEY = _oa_obj(
    {
        "currency": _OA_STRING,
        "units": _OA_STRING,
        "nano": _OA_INT,
        "amount": _OA_STRING,
    }
)

_OA_ACCOUNT = _oa_obj(
    {
        "masked_id": _OA_STRING,
        "name": _OA_STRING,
        "type": _OA_STRING,
        "status": _OA_STRING,
        "access_level": _OA_STRING,
    }
)

_OA_POSITION = _oa_obj(
    {
        "instrument_uid": _OA_STRING,
        "position_uid": _OA_STRING,
        "figi": _OA_STRING,
        "instrument_type": _OA_STRING,
        "quantity": _OA_STRING,
        "quantity_lots": _OA_STRING,
        "balance": _OA_STRING,
        "blocked": _OA_STRING,
        "current_price": _OA_MONEY,
        "average_position_price": _OA_MONEY,
        "expected_yield": _OA_MONEY,
    }
)

_OA_PORTFOLIO = _oa_obj(
    {
        "positions": _oa_array(_OA_POSITION),
        "virtual_positions": _oa_array(_OA_POSITION),
        "total_amount_portfolio": _OA_MONEY,
        "total_amount_shares": _OA_MONEY,
        "total_amount_bonds": _OA_MONEY,
        "total_amount_etf": _OA_MONEY,
        "total_amount_currencies": _OA_MONEY,
        "expected_yield": _OA_MONEY,
    }
)

_OA_POSITIONS = _oa_obj(
    {
        "money": _oa_array(_OA_MONEY),
        "blocked": _oa_array(_OA_MONEY),
        "securities": _oa_array(_OA_POSITION),
        "futures": _oa_array(_OA_POSITION),
        "options": _oa_array(_OA_POSITION),
    }
)

_OA_WITHDRAW_LIMITS = _oa_obj(
    {
        "money": _oa_array(_OA_MONEY),
        "blocked": _oa_array(_OA_MONEY),
        "blocked_guarantee": _oa_array(_OA_MONEY),
    }
)

_OA_IDENTITY_CHECK = _oa_obj(
    {
        "overall": _OA_STRING,
        "matches": _OA_INT,
        "conflicts": _OA_INT,
        "fields": _oa_obj(
            {
                "instrument_uid": _OA_STRING,
                "position_uid": _OA_STRING,
                "figi": _OA_STRING,
            }
        ),
    }
)

_OA_INSTRUMENT = _oa_obj(
    {
        "name": _OA_STRING,
        "ticker": _OA_STRING,
        "isin": _OA_STRING,
        "figi": _OA_STRING,
        "uid": _OA_STRING,
        "position_uid": _OA_STRING,
        "class_code": _OA_STRING,
        "instrument_type": _OA_STRING,
        "instrument_kind": _OA_STRING,
        "lot": _OA_INT,
        "currency": _OA_STRING,
        "api_trade_available_flag": _OA_BOOL,
        "buy_available_flag": _OA_BOOL,
        "sell_available_flag": _OA_BOOL,
    }
)

_OA_ENRICHED_POSITION = _oa_obj(
    {
        "instrument_uid": _OA_STRING,
        "position_uid": _OA_STRING,
        "figi": _OA_STRING,
        "enrichment_status": _OA_STRING,
        "instrument_metadata": _OA_INSTRUMENT,
        "identity_check": _OA_IDENTITY_CHECK,
    }
)

_OA_RESOLUTION = _oa_obj(
    {
        "source": _OA_STRING,
        "cache_hit": _OA_BOOL,
        "api_calls": _OA_INT,
        "identifier_type": _OA_STRING,
        "identifier": _OA_STRING,
    }
)

_OA_DIRECTORY_ENTRY = _oa_obj(
    {
        "status": _OA_STRING,
        "reference": _oa_obj(
            {
                "identity": _OA_STRING,
                "instrument_uid": _OA_STRING,
                "position_uid": _OA_STRING,
                "figi": _OA_STRING,
                "ticker": _OA_STRING,
                "class_code": _OA_STRING,
            }
        ),
        "resolution": _OA_RESOLUTION,
        "identity_check": _OA_IDENTITY_CHECK,
        "instrument": _OA_INSTRUMENT,
    }
)

_OA_ORDER_LEVEL = _oa_obj(
    {
        "price": _OA_STRING,
        "quantity_lots": _OA_INT,
    }
)

_OA_LAST_PRICE = _oa_obj(
    {
        "status": _OA_STRING,
        "price": _OA_STRING,
        "time": _OA_STRING,
        "age_seconds": _OA_NUMBER,
        "instrument_uid": _OA_STRING,
        "figi": _OA_STRING,
        "last_price_type": _OA_STRING,
        "reason": _OA_STRING,
    }
)

_OA_TRADING_STATUS = _oa_obj(
    {
        "status": _OA_STRING,
        "trading_status": _OA_STRING,
        "limit_order_available_flag": _OA_BOOL,
        "market_order_available_flag": _OA_BOOL,
        "api_trade_available_flag": _OA_BOOL,
        "bestprice_order_available_flag": _OA_BOOL,
        "only_best_price": _OA_BOOL,
        "instrument_uid": _OA_STRING,
        "figi": _OA_STRING,
    }
)

_OA_ORDER_BOOK = _oa_obj(
    {
        "status": _OA_STRING,
        "requested_depth": _OA_INT,
        "returned_bid_levels": _OA_INT,
        "returned_ask_levels": _OA_INT,
        "depth": _OA_INT,
        "instrument_uid": _OA_STRING,
        "figi": _OA_STRING,
        "time": _OA_STRING,
        "age_seconds": _OA_NUMBER,
        "best_bid": _OA_ORDER_LEVEL,
        "best_ask": _OA_ORDER_LEVEL,
        "spread": _oa_obj(
            {
                "absolute": _OA_STRING,
                "percent_of_midpoint": _OA_STRING,
            }
        ),
        "bids": _oa_array(_OA_ORDER_LEVEL),
        "asks": _oa_array(_OA_ORDER_LEVEL),
        "last_price": _OA_STRING,
        "close_price": _OA_STRING,
        "limit_up": _OA_STRING,
        "limit_down": _OA_STRING,
    }
)

_OA_OPERATION = _oa_obj(
    {
        "date": _OA_STRING,
        "type": _OA_STRING,
        "category": _OA_STRING,
        "state": _OA_STRING,
        "name": _OA_STRING,
        "description": _OA_STRING,
        "instrument_uid": _OA_STRING,
        "position_uid": _OA_STRING,
        "figi": _OA_STRING,
        "payment": _OA_MONEY,
        "price": _OA_MONEY,
        "commission": _OA_MONEY,
        "quantity": _OA_STRING,
        "quantity_done": _OA_STRING,
    }
)

_ACTION_200_SCHEMAS: dict[str, dict[str, Any]] = {
    "/health": _oa_obj(
        {
            "status": _OA_STRING,
            "service": _OA_STRING,
            "version": _OA_STRING,
            "time_utc": _OA_STRING,
            "tls_mode": _OA_STRING,
            "python_version": _OA_STRING,
            "sdk_version": _OA_STRING,
            "protobuf_version": _OA_STRING,
            "grpcio_version": _OA_STRING,
            "configured": _oa_obj(
                {
                    "tinvest_token": _OA_BOOL,
                    "gateway_api_key": _OA_BOOL,
                }
            ),
            "capabilities": _oa_array(_OA_STRING),
            "trading_methods": _OA_BOOL,
        },
        required=["status", "service", "version"],
    ),
    "/connection": _oa_obj(
        {
            "status": _OA_STRING,
            "retrieved_at": _OA_STRING,
            "account": _OA_ACCOUNT,
        },
        required=["status", "retrieved_at", "account"],
    ),
    "/snapshot": _oa_obj(
        {
            "status": _OA_STRING,
            "retrieved_at": _OA_STRING,
            "account": _OA_ACCOUNT,
            "portfolio": _OA_PORTFOLIO,
            "positions": _OA_POSITIONS,
            "withdraw_limits": _OA_WITHDRAW_LIMITS,
            "warnings": _oa_array(_OA_STRING),
        },
        required=["status", "retrieved_at", "account"],
    ),
    "/snapshot/enriched": _oa_obj(
        {
            "status": _OA_STRING,
            "version": _OA_STRING,
            "retrieved_at": _OA_STRING,
            "account": _OA_ACCOUNT,
            "portfolio": _OA_PORTFOLIO,
            "positions": _OA_POSITIONS,
            "withdraw_limits": _OA_WITHDRAW_LIMITS,
            "enriched_portfolio_positions": _oa_array(_OA_ENRICHED_POSITION),
            "enriched_virtual_positions": _oa_array(_OA_ENRICHED_POSITION),
            "enriched_balances": _oa_obj(
                {
                    "securities": _oa_array(_OA_ENRICHED_POSITION),
                    "futures": _oa_array(_OA_ENRICHED_POSITION),
                    "options": _oa_array(_OA_ENRICHED_POSITION),
                }
            ),
            "instrument_directory": _oa_array(_OA_DIRECTORY_ENTRY),
            "enrichment_quality": _oa_obj(
                {
                    "position_occurrences": _OA_INT,
                    "unique_instrument_references": _OA_INT,
                    "references_resolved": _OA_INT,
                    "references_unresolved": _OA_INT,
                    "cache_hits": _OA_INT,
                    "instrument_api_calls": _OA_INT,
                    "identity_conflicts": _OA_INT,
                }
            ),
            "warnings": _oa_array(_OA_STRING),
        },
        required=["status", "version", "retrieved_at"],
    ),
    "/instruments/search": _oa_obj(
        {
            "status": _OA_STRING,
            "search_mode": _OA_STRING,
            "retrieved_at": _OA_STRING,
            "query": _OA_STRING,
            "filters": _oa_obj(
                {
                    "instrument_type": _OA_STRING,
                    "api_trade_available_only": _OA_BOOL,
                    "exact_only": _OA_BOOL,
                }
            ),
            "raw_candidates": _OA_INT,
            "deduplicated_candidates": _OA_INT,
            "returned_candidates": _OA_INT,
            "truncated": _OA_BOOL,
            "quality": _oa_obj(
                {
                    "duplicates_removed": _OA_INT,
                    "exact_matches": _OA_INT,
                    "type_filtered_out": _OA_INT,
                    "api_filtered_out": _OA_INT,
                }
            ),
            "best_match": _OA_INSTRUMENT,
            "instruments": _oa_array(_OA_INSTRUMENT),
            "warnings": _oa_array(_OA_STRING),
        },
        required=["status", "retrieved_at", "query"],
    ),
    "/market/snapshot": _oa_obj(
        {
            "status": _OA_STRING,
            "version": _OA_STRING,
            "retrieved_at": _OA_STRING,
            "instrument_uid": _OA_STRING,
            "components": _oa_obj(
                {
                    "instrument_reference": _OA_STRING,
                    "last_price": _OA_STRING,
                    "trading_status": _OA_STRING,
                    "order_book": _OA_STRING,
                }
            ),
            "instrument_reference": _OA_DIRECTORY_ENTRY,
            "last_price": _OA_LAST_PRICE,
            "trading_status": _OA_TRADING_STATUS,
            "order_book": _OA_ORDER_BOOK,
            "estimated_lot_values": _oa_obj(
                {
                    "lot": _OA_STRING,
                    "currency": _OA_STRING,
                    "instrument_kind": _OA_STRING,
                    "calculation_basis": _OA_STRING,
                    "estimated_value_per_lot": _oa_obj(
                        {
                            "last_price": _OA_STRING,
                            "best_bid": _OA_STRING,
                            "best_ask": _OA_STRING,
                        }
                    ),
                }
            ),
            "warnings": _oa_array(_OA_STRING),
        },
        required=["status", "version", "retrieved_at", "instrument_uid"],
    ),
    "/operations": _oa_obj(
        {
            "status": _OA_STRING,
            "retrieved_at": _OA_STRING,
            "period": _oa_obj(
                {
                    "from": _OA_STRING,
                    "to": _OA_STRING,
                    "days": _OA_INT,
                }
            ),
            "account": _OA_ACCOUNT,
            "pagination": _oa_obj(
                {
                    "pages_loaded": _OA_INT,
                    "page_limit": _OA_INT,
                    "truncated": _OA_BOOL,
                }
            ),
            "quality": _oa_obj(
                {
                    "raw_items_loaded": _OA_INT,
                    "items_outside_period": _OA_INT,
                    "duplicates_removed": _OA_INT,
                    "returned_items": _OA_INT,
                }
            ),
            "state_counts": _oa_obj(
                {
                    "OPERATION_STATE_EXECUTED": _OA_INT,
                    "OPERATION_STATE_CANCELED": _OA_INT,
                    "OPERATION_STATE_PROGRESS": _OA_INT,
                }
            ),
            "category_counts": _oa_obj(
                {
                    "deposit": _OA_INT,
                    "withdrawal": _OA_INT,
                    "buy": _OA_INT,
                    "sell": _OA_INT,
                    "commission": _OA_INT,
                    "tax": _OA_INT,
                    "coupon": _OA_INT,
                    "dividend": _OA_INT,
                    "other": _OA_INT,
                }
            ),
            "executed_cash_summary": _oa_obj(
                {
                    "deposit": _oa_obj({"RUB": _oa_obj({"net": _OA_STRING, "inflow": _OA_STRING, "outflow": _OA_STRING})}),
                    "withdrawal": _oa_obj({"RUB": _oa_obj({"net": _OA_STRING, "inflow": _OA_STRING, "outflow": _OA_STRING})}),
                    "buy": _oa_obj({"RUB": _oa_obj({"net": _OA_STRING, "inflow": _OA_STRING, "outflow": _OA_STRING})}),
                    "sell": _oa_obj({"RUB": _oa_obj({"net": _OA_STRING, "inflow": _OA_STRING, "outflow": _OA_STRING})}),
                }
            ),
            "operations": _oa_array(_OA_OPERATION),
            "warnings": _oa_array(_OA_STRING),
        },
        required=["status", "retrieved_at", "period", "account"],
    ),
}


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    schema["servers"] = app.servers

    for path, response_schema in _ACTION_200_SCHEMAS.items():
        operation = schema.get("paths", {}).get(path, {}).get("get")
        if not isinstance(operation, dict):
            continue
        response_200 = operation.setdefault("responses", {}).setdefault(
            "200", {"description": "Successful Response"}
        )
        response_200["content"] = {
            "application/json": {"schema": response_schema}
        }

    # The GPT Actions validator also checks nested object schemas generated by
    # FastAPI (for example ValidationError.ctx). JSON Schema allows an empty
    # `properties` object, so add it wherever FastAPI emitted only type=object.
    def ensure_object_properties(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" not in node:
                node["properties"] = {}
            for child in node.values():
                ensure_object_properties(child)
        elif isinstance(node, list):
            for child in node:
                ensure_object_properties(child)

    ensure_object_properties(schema)

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
