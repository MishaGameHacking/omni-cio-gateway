import hmac
import os
from datetime import datetime, timezone
from typing import Any

# T-Bank SDK reads this variable when configuring TLS verification.
# The SDK uses its embedded certificate bundle; nothing is installed system-wide.
os.environ.setdefault("SSL_TBANK_VERIFY", "True")

import grpc
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.protobuf.json_format import MessageToDict
from t_tech.invest import Client


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
    version="1.0.0",
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


def proto_to_dict(message: Any) -> dict[str, Any]:
    """Convert protobuf response to JSON-compatible dict."""
    return MessageToDict(
        message,
        preserving_proto_field_name=True,
        use_integers_for_enums=False,
    )


def mask_account_id(account_id: str) -> str:
    if not account_id:
        return "***"
    return f"***{account_id[-4:]}"


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
    accounts_data = proto_to_dict(accounts_response)
    accounts = accounts_data.get("accounts", [])

    open_accounts = [
        account
        for account in accounts
        if "OPEN" in str(account.get("status", "")).upper()
    ]

    if not open_accounts:
        raise HTTPException(
            status_code=404,
            detail={"code": "NO_OPEN_ACCOUNT"},
        )

    if len(open_accounts) > 1:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "MULTIPLE_OPEN_ACCOUNTS",
                "accounts": [
                    {
                        "masked_id": mask_account_id(str(account.get("id", ""))),
                        "name": account.get("name"),
                        "type": account.get("type"),
                    }
                    for account in open_accounts
                ],
                "message": (
                    "Create a T-Invest token restricted to one account "
                    "or extend the gateway with account aliases."
                ),
            },
        )

    account = open_accounts[0]
    account_id = str(account.get("id", ""))
    if not account_id:
        raise HTTPException(
            status_code=502,
            detail={"code": "ACCOUNT_ID_MISSING"},
        )

    safe_account = {
        "masked_id": mask_account_id(account_id),
        "name": account.get("name"),
        "type": account.get("type"),
        "status": account.get("status"),
        "access_level": account.get("access_level"),
    }
    return account_id, safe_account


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
        raise HTTPException(
            status_code=502,
            detail={
                "code": "GATEWAY_CLIENT_ERROR",
                "message": type(exc).__name__,
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
                currency="RUB",
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
        raise HTTPException(
            status_code=502,
            detail={
                "code": "GATEWAY_CLIENT_ERROR",
                "message": type(exc).__name__,
            },
        ) from exc
