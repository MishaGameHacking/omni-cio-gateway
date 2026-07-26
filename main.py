import hmac
import logging
import os
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from importlib import metadata
from typing import Any

# T-Bank SDK reads this variable when configuring TLS verification.
# The SDK uses its embedded certificate bundle; nothing is installed system-wide.
os.environ.setdefault("SSL_TBANK_VERIFY", "True")

import grpc
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.protobuf.json_format import MessageToDict
from t_tech.invest import Client


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
    version="1.0.2",
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


def proto_to_dict(message: Any) -> dict[str, Any]:
    """Convert protobuf/dataclass/dict responses to JSON-compatible dicts."""
    if isinstance(message, dict):
        return message

    if hasattr(message, "DESCRIPTOR"):
        return MessageToDict(
            message,
            preserving_proto_field_name=True,
            use_integers_for_enums=False,
        )

    to_dict = getattr(message, "to_dict", None)
    if callable(to_dict):
        result = to_dict()
        if isinstance(result, dict):
            return result

    if is_dataclass(message):
        result = asdict(message)
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
