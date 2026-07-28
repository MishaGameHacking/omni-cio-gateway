from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from . import TELEGRAM_COMPANION_VERSION


_STATUS_ICONS = {
    "ok": "✅",
    "matched": "✅",
    "passed": "✅",
    "ready": "✅",
    "pending": "⏳",
    "partial": "⚠️",
    "warning": "⚠️",
    "degraded": "⚠️",
    "error": "❌",
    "failed": "❌",
    "unavailable": "⚪",
}

_CATEGORY_LABELS = {
    "deposits": "Пополнения",
    "withdrawals": "Выводы",
    "purchases": "Покупки",
    "sales": "Продажи",
    "broker_commissions": "Комиссии брокера",
    "service_fees": "Сервисные комиссии",
    "margin_fees": "Маржинальные комиссии",
    "other_fees": "Прочие комиссии",
    "taxes": "Налоги",
    "coupons": "Купоны",
    "dividends": "Дивиденды",
    "bond_redemptions": "Погашения облигаций",
    "other": "Прочие операции",
}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dig(value: Any, *path: str, default: Any = None) -> Any:
    current = value
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _first(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return default


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, dict):
        units = value.get("units")
        nano = value.get("nano")
        if units is not None or nano is not None:
            try:
                return Decimal(str(units or 0)) + Decimal(str(nano or 0)) / Decimal("1000000000")
            except (InvalidOperation, ValueError, TypeError):
                return None
        for key in ("amount", "value", "price", "reported_money", "net_payment"):
            if key in value:
                return _decimal(value[key])
        return None
    try:
        return Decimal(str(value).replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _number(value: Any, *, decimals: int = 2) -> str:
    parsed = _decimal(value)
    if parsed is None:
        return "—"
    quantizer = Decimal("1") if parsed == parsed.to_integral() else Decimal("1").scaleb(-decimals)
    rendered = f"{parsed.quantize(quantizer):f}"
    integer, dot, fraction = rendered.partition(".")
    sign = ""
    if integer.startswith("-"):
        sign, integer = "-", integer[1:]
    grouped = " ".join(
        integer[max(0, len(integer) - offset - 3) : len(integer) - offset]
        for offset in range(0, len(integer), 3)
    )[::-1]
    # The reverse-group expression reverses characters inside groups; rebuild safely.
    groups: list[str] = []
    while integer:
        groups.append(integer[-3:])
        integer = integer[:-3]
    grouped = " ".join(reversed(groups)) or "0"
    if dot and fraction:
        fraction = fraction.rstrip("0")
        if fraction:
            return f"{sign}{grouped},{fraction}"
    return f"{sign}{grouped}"


def _currency(value: Any, *, default: str = "RUB") -> str:
    text = str(value or default).strip().upper()
    return text or default


def _money(value: Any, currency: Any = "RUB") -> str:
    parsed = _decimal(value)
    if parsed is None:
        return "—"
    code = _currency(currency)
    suffix = "₽" if code == "RUB" else code
    return f"{_number(parsed)} {suffix}"


def _money_node(value: Any, *, default_currency: str = "RUB") -> str:
    if isinstance(value, dict):
        currency = _first(value.get("currency"), value.get("currency_code"), default=default_currency)
        return _money(value, currency)
    return _money(value, default_currency)


def _yes_no(value: Any) -> str:
    if value is True:
        return "да"
    if value is False:
        return "нет"
    return "—"


def _icon(status: Any) -> str:
    return _STATUS_ICONS.get(str(status or "").lower(), "ℹ️")


def _account(payload: dict[str, Any]) -> tuple[str, str, str, str]:
    account = _dict(payload.get("account"))
    masked = str(
        _first(
            account.get("masked_id"),
            payload.get("masked_account"),
            payload.get("account_masked_id"),
            default="—",
        )
    )
    name = str(_first(account.get("name"), account.get("type"), default=""))
    status = str(_first(account.get("status"), payload.get("account_status"), default=""))
    access = str(_first(account.get("access_level"), payload.get("access_level"), default=""))
    return masked, name, status, access


def format_gateway_health(payload: dict[str, Any]) -> str:
    status = str(payload.get("status") or "unknown")
    trading = payload.get("trading_methods")
    build = _dict(payload.get("build"))
    lines = [
        f"{_icon(status)} Omni-CIO Gateway",
        f"Статус: {status}",
        f"Gateway: v{payload.get('version', '—')}",
        f"Telegram: v{TELEGRAM_COMPANION_VERSION}",
    ]
    if build.get("entrypoint"):
        lines.append(f"Entrypoint: {build['entrypoint']}")
    lines.extend(
        [
            "Режим: только чтение",
            f"Торговые методы: {'выключены' if trading is False else 'не подтверждено'}",
        ]
    )
    return "\n".join(lines)


def format_system_status(
    health: dict[str, Any],
    connection: dict[str, Any] | None,
    *,
    connection_error: str | None = None,
) -> str:
    gateway_status = str(health.get("status") or "unknown")
    lines = [
        "🧭 Статус Omni-CIO",
        f"Telegram: ✅ работает · v{TELEGRAM_COMPANION_VERSION}",
        f"Gateway: {_icon(gateway_status)} {gateway_status} · v{health.get('version', '—')}",
    ]
    if connection is not None:
        conn_status = str(connection.get("status") or "unknown")
        masked, name, _status, access = _account(connection)
        lines.append(f"T-Invest: {_icon(conn_status)} {conn_status}")
        lines.append(f"Счёт: {masked}{f' · {name}' if name else ''}")
        if access:
            lines.append(f"Доступ: {access}")
    elif connection_error:
        lines.append(f"T-Invest: ⚠️ {connection_error}")
    lines.extend(["Режим: только чтение", "Торговые методы: выключены"])
    return "\n".join(lines)


def format_connection(payload: dict[str, Any]) -> str:
    status = str(payload.get("status") or "unknown")
    masked, name, account_status, access = _account(payload)
    lines = [f"{_icon(status)} Подключение к T-Invest", f"Статус: {status}"]
    lines.append(f"Счёт: {masked}{f' · {name}' if name else ''}")
    if account_status:
        lines.append(f"Состояние счёта: {account_status}")
    if access:
        lines.append(f"Доступ: {access}")
    lines.extend([f"Gateway: v{payload.get('version', '—')}", "Торговые методы: выключены"])
    return "\n".join(lines)


def _portfolio_positions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    portfolio = _dict(payload.get("portfolio"))
    candidates = _first(portfolio.get("positions"), payload.get("portfolio_positions"), payload.get("positions"), default=[])
    return [item for item in _list(candidates) if isinstance(item, dict)]


def _cash_from_snapshot(payload: dict[str, Any]) -> list[tuple[str, Decimal]]:
    positions = _dict(payload.get("positions"))
    money_rows = _list(positions.get("money"))
    totals: list[tuple[str, Decimal]] = []
    for row in money_rows:
        if not isinstance(row, dict):
            continue
        amount = _decimal(row)
        if amount is None:
            continue
        totals.append((_currency(row.get("currency")), amount))
    if totals:
        return totals
    for row in _portfolio_positions(payload):
        if str(row.get("instrument_type") or "").lower() not in {"currency", "cash"}:
            continue
        amount = _decimal(_first(row.get("quantity"), row.get("current_price"), row))
        if amount is not None:
            totals.append((_currency(row.get("currency")), amount))
    return totals


def format_portfolio(payload: dict[str, Any]) -> str:
    status = str(payload.get("status") or "unknown")
    masked, name, _account_status, access = _account(payload)
    portfolio = _dict(payload.get("portfolio"))
    positions = _portfolio_positions(payload)
    market_positions = [
        row
        for row in positions
        if str(row.get("instrument_type") or "").lower() not in {"currency", "cash"}
    ]
    total = _first(
        portfolio.get("total_amount_portfolio"),
        payload.get("total_amount_portfolio"),
        default=None,
    )
    lines = [f"{_icon(status)} Портфель", f"Счёт: {masked}{f' · {name}' if name else ''}"]
    if total is not None:
        lines.append(f"Общая стоимость: {_money_node(total)}")
    cash_rows = _cash_from_snapshot(payload)
    if cash_rows:
        lines.append("Деньги: " + ", ".join(_money(amount, currency) for currency, amount in cash_rows))
    lines.append(f"Рыночных позиций: {len(market_positions)}")
    for row in market_positions[:5]:
        title = str(_first(row.get("name"), row.get("ticker"), row.get("instrument_uid"), row.get("figi"), default="Инструмент"))
        quantity = _first(row.get("quantity"), row.get("quantity_lots"), row.get("units"), default="—")
        current_price = row.get("current_price")
        detail = f" • {title}: {_number(quantity)}"
        if current_price not in (None, {}, ""):
            detail += f" · {_money_node(current_price, default_currency=_currency(row.get('currency')))}"
        lines.append(detail)
    if len(market_positions) > 5:
        lines.append(f"…ещё {len(market_positions) - 5}")
    if access:
        lines.append(f"Доступ: {access}")
    lines.extend([f"Gateway: v{payload.get('version', '—')}", "Торговые методы: выключены"])
    return "\n".join(lines)


def format_cash(payload: dict[str, Any]) -> str:
    status = str(payload.get("status") or "unknown")
    masked, _name, _account_status, _access = _account(payload)
    lines = [f"{_icon(status)} Деньги и ликвидность", f"Счёт: {masked}"]
    rows = [row for row in _list(payload.get("cash_by_currency")) if isinstance(row, dict)]
    if not rows:
        lines.append("Денежные строки не получены.")
    for row in rows:
        currency = _currency(row.get("currency"))
        lines.append(f"\n{currency}")
        lines.append(f"На счёте: {_money(row.get('reported_money'), currency)}")
        if row.get("withdrawable_money") not in (None, "unavailable"):
            lines.append(f"Доступно к выводу: {_money(row.get('withdrawable_money'), currency)}")
        if row.get("cash_difference") not in (None, "unavailable"):
            lines.append(f"Расхождение: {_money(row.get('cash_difference'), currency)}")
        if row.get("cash_status"):
            lines.append(f"Сверка: {_icon(row.get('cash_status'))} {row.get('cash_status')}")
    buying_power = _dict(payload.get("buying_power"))
    if buying_power:
        lines.append(f"\nПокупательная способность подтверждена: {_yes_no(buying_power.get('confirmed'))}")
    quality = _dict(payload.get("quality"))
    if "complete" in quality:
        lines.append(f"Данные полные: {_yes_no(quality.get('complete'))}")
    lines.append("Торговые методы: выключены")
    return "\n".join(lines)


def format_analytics(payload: dict[str, Any]) -> str:
    status = str(payload.get("status") or "unknown")
    masked, _name, _account_status, _access = _account(payload)
    lines = [f"{_icon(status)} Аналитика портфеля", f"Счёт: {masked}"]
    summaries = [row for row in _list(payload.get("summary_by_currency")) if isinstance(row, dict)]
    if not summaries:
        lines.append("Сводка по валютам отсутствует.")
    for row in summaries:
        currency = _currency(row.get("currency"))
        lines.append(f"\n{currency}")
        lines.append(f"Портфель: {_money(row.get('portfolio_value'), currency)}")
        lines.append(f"Деньги: {_money(row.get('cash_value'), currency)} ({row.get('cash_share_percent', '—')}%)")
        lines.append(f"Ценные бумаги: {_money(row.get('securities_value'), currency)} ({row.get('securities_share_percent', '—')}%)")
        if row.get("valuation_coverage_percent") is not None:
            lines.append(f"Покрытие оценкой: {row.get('valuation_coverage_percent')}%")
        concentration = row.get("top_n_concentration_percent")
        if concentration not in (None, "unavailable"):
            lines.append(f"Концентрация top-{row.get('top_n', 5)}: {concentration}%")
    quality = _dict(payload.get("quality"))
    if quality:
        lines.append(f"\nДанные полные: {_yes_no(quality.get('complete_for_selected_basis'))}")
        lines.append(f"Ошибок компонентов: {quality.get('component_errors', '—')}")
    lines.append("Торговые методы: выключены")
    return "\n".join(lines)


def _category_amount(row: dict[str, Any]) -> Any:
    inflow = _decimal(row.get("inflow")) or Decimal("0")
    outflow = _decimal(row.get("outflow")) or Decimal("0")
    if inflow:
        return inflow
    if outflow:
        return outflow
    return _first(row.get("amount"), row.get("net_payment"), default=0)


def format_operations(payload: dict[str, Any], *, days: int) -> str:
    status = str(payload.get("status") or "unknown")
    masked, _name, _account_status, _access = _account(payload)
    period = _dict(payload.get("period"))
    lines = [
        f"{_icon(status)} Операции за {period.get('days', days)} дн.",
        f"Счёт: {masked}",
        f"Операций: {payload.get('operations_count', 0)} · исполнено: {payload.get('executed_operations', 0)}",
    ]
    category_counts = _dict(payload.get("category_counts"))
    summaries = [row for row in _list(payload.get("cash_summary_by_currency")) if isinstance(row, dict)]
    for currency_row in summaries:
        currency = _currency(currency_row.get("currency"))
        non_zero: list[str] = []
        for key, label in _CATEGORY_LABELS.items():
            category = _dict(currency_row.get(key))
            count = int(category.get("count", 0) or 0)
            if count <= 0:
                continue
            non_zero.append(f"{label}: {_money(_category_amount(category), currency)} ({count})")
        if non_zero:
            lines.append(f"\n{currency}")
            lines.extend(f"• {item}" for item in non_zero)
    if not any(int(value or 0) for value in category_counts.values() if isinstance(value, (int, float, str)) and str(value).lstrip('-').isdigit()):
        lines.append("Денежных операций за период нет.")
    net_flows = [row for row in _list(payload.get("net_external_flow")) if isinstance(row, dict)]
    for row in net_flows:
        lines.append(f"Чистый внешний поток: {_money(row.get('net_external_flow'), row.get('currency'))}")
    reconciliation = _dict(payload.get("reconciliation"))
    lines.append(f"Сверка: {_icon(reconciliation.get('status'))} {reconciliation.get('status', '—')}")
    quality = _dict(payload.get("quality"))
    lines.append(f"Данные полные: {_yes_no(_first(payload.get('complete'), quality.get('complete'), default=None))}")
    lines.append("Торговые методы: выключены")
    return "\n".join(lines)


def format_report(payload: dict[str, Any], *, status_command: bool = False) -> str:
    status = str(payload.get("status") or "unknown")
    title = "Статус брокерского отчёта" if status_command else "Брокерский отчёт"
    generation = _dict(payload.get("report_generation"))
    task_id = str(generation.get("task_id") or "").strip()
    period = _dict(payload.get("period"))
    lines = [f"{_icon(status)} {title}", f"Статус: {status}"]
    if period:
        lines.append(f"Период: {period.get('from', '—')} — {period.get('to', '—')}")
    if task_id:
        lines.append(f"task_id: {task_id}")
    if status == "pending":
        lines.append("Отчёт ещё формируется.")
        lines.append("Повторите /report_status через 10–30 секунд.")
        return "\n".join(lines)
    if status == "ok":
        broker = _dict(payload.get("broker_report_summary"))
        operations = _dict(payload.get("operations_summary"))
        trade = _dict(payload.get("trade_reconciliation"))
        reconciliation = _dict(payload.get("reconciliation"))
        lines.append(f"Строк отчёта: {broker.get('rows', '—')}")
        lines.append(f"Операций API: {operations.get('operations_count', '—')}")
        if trade:
            lines.append(f"Сделки: {_icon(trade.get('status'))} {trade.get('status', '—')}")
        lines.append(f"Общая сверка: {_icon(reconciliation.get('status'))} {reconciliation.get('status', '—')}")
        lines.append(f"Данные полные: {_yes_no(payload.get('complete'))}")
    else:
        errors = [item for item in _list(payload.get("component_errors")) if isinstance(item, dict)]
        if errors:
            first_error = errors[0]
            lines.append(f"Ошибка: {_first(first_error.get('message'), _dig(first_error, 'error', 'message'), default='неизвестно')}")
    lines.append("Торговые методы: выключены")
    return "\n".join(lines)
