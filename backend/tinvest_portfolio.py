"""Read-only T-Invest portfolio aggregation for the Analyst AI Android app."""
from __future__ import annotations

import ssl
from decimal import Decimal
from typing import Annotated, Any

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query

try:  # Package import in tests.
    from . import app as backend
    from .volume_contract import decimal as strict_decimal
except ImportError:  # Top-level import under uvicorn from /opt/analyst-ai/backend.
    import app as backend  # type: ignore[no-redef]
    from volume_contract import decimal as strict_decimal

router = APIRouter()

TINVEST_PORTFOLIO_URL = (
    "https://invest-public-api.tbank.ru/rest/"
    "tinkoff.public.invest.api.contract.v1.OperationsService/GetPortfolio"
)
TINVEST_POSITIONS_URL = (
    "https://invest-public-api.tbank.ru/rest/"
    "tinkoff.public.invest.api.contract.v1.OperationsService/GetPositions"
)
SUPPORTED_CURRENCIES = {"RUB", "USD", "EUR"}

ALLOCATION_FIELDS = (
    ("Акции", "totalAmountShares"),
    ("Облигации", "totalAmountBonds"),
    ("Фонды", "totalAmountEtf"),
    ("Валюта и деньги", "totalAmountCurrencies"),
    ("Фьючерсы", "totalAmountFutures"),
    ("Опционы", "totalAmountOptions"),
    ("Структурные продукты", "totalAmountSp"),
    ("Цифровые активы", "totalAmountDfa"),
)

ACCOUNT_TYPE_NAMES = {
    "ACCOUNT_TYPE_TINKOFF": "Брокерский счёт",
    "ACCOUNT_TYPE_TINKOFF_IIS": "ИИС",
    "ACCOUNT_TYPE_INVEST_BOX": "Инвесткопилка",
}

INSTRUMENT_TYPE_NAMES = {
    "share": "Акция",
    "bond": "Облигация",
    "etf": "Фонд",
    "currency": "Валюта",
    "futures": "Фьючерс",
    "option": "Опцион",
    "sp": "Структурный продукт",
    "dfa": "Цифровой актив",
}

CURRENCY_NAMES = {
    "RUB": "Рубль",
    "USD": "Доллар США",
    "EUR": "Евро",
    "CNY": "Юань",
    "HKD": "Гонконгский доллар",
    "CHF": "Швейцарский франк",
    "GBP": "Фунт стерлингов",
}


def _decimal(value: Any) -> Decimal:
    # Protobuf may omit an optional zero-valued allocation. A PRESENT malformed
    # quotation must never silently erase capital, a position or its risk.
    if value is None:
        return Decimal(0)
    amount = strict_decimal({"units": value.get("units", 0), "nano": value.get("nano", 0)}) if isinstance(value, dict) else None
    if amount is None:
        raise HTTPException(502, "tinvest_invalid_quotation")
    return amount


def _decimal_payload(value: Decimal) -> dict[str, int]:
    units = int(value)
    nano = int((value - Decimal(units)) * Decimal(1_000_000_000))
    return {"units": units, "nano": nano}


def _money_payload(value: Decimal, currency: str) -> dict[str, Any]:
    return {
        "value": _decimal_payload(value),
        "currency": currency.upper(),
    }


def _money_decimal(value: Any) -> tuple[Decimal, str]:
    if value is None:
        return Decimal(0), ""
    if not isinstance(value, dict):
        raise HTTPException(502, "tinvest_invalid_money")
    return _decimal(value), str(value.get("currency") or "").upper()


def _all_time_profit(
    current_value: Decimal,
    yield_percent: Decimal,
) -> Decimal | None:
    """Recover absolute all-time profit from current value and relative yield.

    T-Invest exposes the all-time relative result as ``expectedYield`` but only
    exposes the absolute ``dailyYield`` for the current day. For the same
    presentation as the T-Invest app, use the identity:

        current = cost_basis * (1 + percent / 100)
        profit = current * percent / (100 + percent)
    """
    denominator = Decimal(100) + yield_percent
    if denominator == 0:
        return None
    return current_value * yield_percent / denominator


def _raise_upstream_status(response: Any) -> None:
    status = int(response.status_code)
    if status in (401, 403):
        raise HTTPException(status_code=422, detail="invalid_tinvest_token")
    if status == 429:
        raise HTTPException(status_code=503, detail="tinvest_rate_limited")
    if status in (408, 504):
        raise HTTPException(status_code=504, detail="tinvest_timeout")
    if status >= 500:
        raise HTTPException(status_code=503, detail="tinvest_upstream_unavailable")
    if status != 200:
        raise HTTPException(status_code=502, detail="tinvest_unexpected_status")


def _post_tinvest(client: Any, url: str, token: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        response = client.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=body,
        )
    except backend.httpx.TimeoutException:
        backend.logger.warning("T-Invest portfolio request timed out")
        raise HTTPException(status_code=504, detail="tinvest_timeout") from None
    except backend.httpx.TransportError as exc:
        transport_details = str(exc).lower()
        is_tls_error = any(
            word in transport_details
            for word in ("certificate", "ssl", "tls", "handshake")
        )
        detail = "tinvest_tls_error" if is_tls_error else "tinvest_connection_failed"
        backend.logger.warning("T-Invest portfolio transport failed (%s)", detail)
        raise HTTPException(status_code=503, detail=detail) from None

    _raise_upstream_status(response)
    try:
        payload = response.json()
    except (ValueError, TypeError):
        raise HTTPException(status_code=502, detail="tinvest_invalid_response") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="tinvest_invalid_response")
    return payload


def _account_name(account: dict[str, Any]) -> str:
    explicit = str(account.get("name") or "").strip()
    if explicit:
        return explicit
    account_type = str(account.get("type") or "")
    return ACCOUNT_TYPE_NAMES.get(account_type, "Инвестиционный счёт")


def _is_readable_account(account: dict[str, Any]) -> bool:
    status = str(account.get("status") or "")
    access = str(account.get("accessLevel") or "")
    return status != "ACCOUNT_STATUS_CLOSED" and access != "ACCOUNT_ACCESS_LEVEL_NO_ACCESS"


def _position_title(position: dict[str, Any], ticker: str | None) -> str:
    explicit = str(position.get("name") or "").strip()
    if explicit:
        return explicit
    if ticker:
        return ticker
    instrument_type = str(position.get("instrumentType") or "").lower()
    return INSTRUMENT_TYPE_NAMES.get(instrument_type, "Инструмент")


def _portfolio_position(raw):
    if not isinstance(raw, dict):
        return None
    identifier = str(
        raw.get("instrumentUid")
        or raw.get("positionUid")
        or raw.get("figi")
        or ""
    ).strip()
    if not identifier:
        return None
    ticker_value = str(raw.get("ticker") or raw.get("figi") or "").strip()
    ticker = ticker_value or None
    instrument_type = str(raw.get("instrumentType") or "").lower()
    if raw.get("quantity") is None:
        raise HTTPException(502, "tinvest_position_quantity_missing")
    quantity = _decimal(raw["quantity"])

    current_value = None
    if instrument_type in {"share", "etf", "currency", "dfa"}:
        price, price_currency = _money_decimal(raw.get("currentPrice"))
        if price_currency and quantity != 0:
            current_value = _money_payload(price * quantity, price_currency)

    return {
        "id": identifier,
        "title": _position_title(raw, ticker),
        "ticker": ticker,
        "quantity": _decimal_payload(quantity),
        "currentValue": current_value,
        # Position expectedYield is an absolute result, not a percentage.
        "expectedYieldPercent": None,
    }


def _portfolio_positions(
    portfolio: dict[str, Any],
    positions: dict[str, Any],
) -> list[dict[str, Any]]:
    result = [item for raw in portfolio.get("positions") or []
              if (item := _portfolio_position(raw)) is not None]
    seen = {item["id"] for item in result}

    for raw_money in positions.get("money") or []:
        if not isinstance(raw_money, dict):
            continue
        amount, currency = _money_decimal(raw_money)
        if not currency or amount == 0:
            continue
        identifier = f"cash:{currency}"
        if identifier in seen:
            continue
        result.append(
            {
                "id": identifier,
                "title": CURRENCY_NAMES.get(currency, currency),
                "ticker": currency,
                "quantity": _decimal_payload(amount),
                "currentValue": _money_payload(amount, currency),
                "expectedYieldPercent": None,
            }
        )
        seen.add(identifier)

    return result


@router.get(
    "/tinvest/portfolio",
    responses={
        400: {"description": "Unsupported display currency."},
        401: {"description": "Analyst AI session is invalid or expired."},
        409: {"description": "T-Invest API is not connected."},
        422: {"description": "T-Invest rejected the stored token."},
        500: {"description": "Stored T-Invest token cannot be decrypted."},
        502: {"description": "Unexpected response from T-Invest."},
        503: {"description": "T-Invest is unavailable or rate limited."},
        504: {"description": "T-Invest request timed out."},
    },
)
def get_tinvest_portfolio(
    currency: Annotated[str, Query()] = "RUB",
    *,
    user: Annotated[Any, Depends(backend.current_user)],
) -> dict[str, Any]:
    selected_currency = currency.upper().strip()
    if selected_currency not in SUPPORTED_CURRENCIES:
        raise HTTPException(status_code=400, detail="unsupported_portfolio_currency")

    encrypted = user["tinvest_token_encrypted"]
    if encrypted is None:
        raise HTTPException(status_code=409, detail="tinvest_not_connected")
    try:
        token = backend.FERNET.decrypt(encrypted).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError):
        backend.logger.exception("Stored T-Invest token cannot be decrypted")
        raise HTTPException(status_code=500, detail="tinvest_token_unreadable") from None

    try:
        ssl_context = backend.tinvest_ssl_context()
        with backend.httpx.Client(
            timeout=backend.httpx.Timeout(20.0, connect=7.0),
            verify=ssl_context,
            follow_redirects=False,
        ) as client:
            portfolios = _read_account_portfolios(client, token, selected_currency)
    except (RuntimeError, ssl.SSLError):
        backend.logger.exception("Unable to initialize verified T-Invest TLS")
        raise HTTPException(status_code=503, detail="tinvest_tls_error") from None

    return _aggregate_portfolios(portfolios, selected_currency)


def _read_account_portfolios(client, token, selected_currency):
    accounts_payload = _post_tinvest(
        client,
        backend.TINVEST_ACCOUNTS_URL,
        token,
        {},
    )
    raw_accounts = accounts_payload.get("accounts")
    if not isinstance(raw_accounts, list):
        raise HTTPException(status_code=502, detail="tinvest_invalid_response")

    result = []
    for account in raw_accounts:
        if not isinstance(account, dict) or not _is_readable_account(account):
            continue
        account_id = str(account.get("id") or "").strip()
        if not account_id:
            continue
        portfolio = _post_tinvest(client, TINVEST_PORTFOLIO_URL, token,
                                  {"accountId": account_id, "currency": selected_currency})
        positions = _post_tinvest(client, TINVEST_POSITIONS_URL, token, {"accountId": account_id})
        _, account_currency = _money_decimal(portfolio.get("totalAmountPortfolio"))
        if account_currency != selected_currency:
            raise HTTPException(502, "tinvest_portfolio_total_currency_invalid")
        result.append((account, account_id, portfolio, positions))
    return result


def _portfolio_yield(portfolio, account_total):
    expected_yield = portfolio.get("expectedYield")
    account_percent = _decimal(expected_yield) if isinstance(expected_yield, dict) else None
    account_profit = None if account_percent is None else _all_time_profit(account_total, account_percent)
    return account_percent, account_profit


def _aggregate_portfolios(portfolios, selected_currency):
    account_results: list[dict[str, Any]] = []
    total_value = Decimal(0)
    total_profit = Decimal(0)
    total_cost_basis = Decimal(0)
    all_yields_known = True
    allocation_totals = {field: Decimal(0) for _, field in ALLOCATION_FIELDS}

    for account, account_id, portfolio, positions in portfolios:
        account_total, _ = _money_decimal(portfolio.get("totalAmountPortfolio"))
        total_value += account_total

        account_percent, account_profit = _portfolio_yield(portfolio, account_total)
        if account_profit is None:
            all_yields_known = False
        else:
            total_profit += account_profit
            total_cost_basis += account_total - account_profit

        for _, field in ALLOCATION_FIELDS:
            allocation_value, _ = _money_decimal(portfolio.get(field))
            allocation_totals[field] += allocation_value

        account_results.append(
            {
                "id": account_id,
                "name": _account_name(account),
                "totalValue": _money_payload(account_total, selected_currency),
                "expectedYieldPercent": (
                    _decimal_payload(account_percent)
                    if account_percent is not None
                    else None
                ),
                "positions": _portfolio_positions(portfolio, positions),
                "limitsLoading": bool(positions.get("limitsLoadingInProgress")),
                "virtualPositionCount": len(portfolio.get("virtualPositions", [])),
            }
        )
    total_percent: Decimal | None = None
    total_profit_payload: dict[str, Any] | None = None
    if account_results and all_yields_known:
        total_profit_payload = _money_payload(total_profit, selected_currency)
        total_percent = (
            (total_profit / total_cost_basis) * Decimal(100)
            if total_cost_basis != 0
            else Decimal(0)
        )

    allocations = _allocation_payload(allocation_totals, total_value)

    return {
        "currency": selected_currency,
        "totalValue": _money_payload(total_value, selected_currency),
        "expectedYieldAmount": total_profit_payload,
        "expectedYieldPercent": (
            _decimal_payload(total_percent) if total_percent is not None else None
        ),
        "accounts": account_results,
        "allocations": allocations,
    }


def _allocation_payload(allocation_totals, total_value):
    allocations = []
    if total_value != 0:
        for title, field in ALLOCATION_FIELDS:
            amount = allocation_totals[field]
            if amount == 0:
                continue
            allocations.append(
                {
                    "title": title,
                    "sharePercent": _decimal_payload(
                        (amount / abs(total_value)) * Decimal(100)
                    ),
                }
            )

    return allocations
