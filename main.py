import hashlib
import hmac
import json
import logging
import os
import sys
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from importlib import metadata
from typing import Any

# T-Bank SDK reads this variable when configuring TLS verification.
# The SDK uses its embedded certificate bundle; nothing is installed system-wide.
os.environ.setdefault("SSL_TBANK_VERIFY", "True")

import grpc
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.protobuf.json_format import MessageToDict
from t_tech.invest import Client, GetOperationsByCursorRequest


logger = logging.getLogger("omni_cio_gateway")

APP_NAME = "omni-cio-readonly-gateway"
TINVEST_TOKEN = os.environ.get("TINVEST_TOKEN", "").strip()
GATEWAY_API_KEY = os.environ.get("GATEWAY_API_KEY", "").strip()

# Render automatically provides the public HTTPS URL of this web service.
# GPT Actions require an explicit absolute server URL in the OpenAPI schema.
PUBLIC_BASE_URL = os.environ.get(
    "RENDER_EXTERNAL_URL",
    "http://localhost:8000",
).rstrip("/")

app = FastAPI(
    title="Omni-CIO Read-Only Gateway",
    version="2.0.3",
    description=(
        "Private read-only gateway between a Custom GPT and T-Invest API. "
        "It exposes only connection and portfolio snapshot endpoints. "
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
        "state": operation_state,
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
        "state": operation.get("state"),
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
        "health": f"{PUBLIC_BASE_URL}/health",
        "openapi": f"{PUBLIC_BASE_URL}/openapi.json",
        "capabilities": ["connection", "portfolio_snapshot", "operations_history"],
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
        "capabilities": ["connection", "portfolio_snapshot", "operations_history"],
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
