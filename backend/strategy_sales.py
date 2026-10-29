"""Read-only reduction proposal for an existing oversized position."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_FLOOR

from fastapi import HTTPException

try:
    from . import volume_purchases as purchases, volume_market as market, portfolio_details as details
    from .volume_contract import decimal, text_number, money, timestamp, financial_context
except ImportError:
    import volume_purchases as purchases
    import volume_market as market
    import portfolio_details as details
    from volume_contract import decimal, text_number, money, timestamp, financial_context


@financial_context
def reduction_lots(current, target, held, blocked, unit_price, lot, visible, broker_max):
    values = (current, target, held, blocked, unit_price)
    if any(value is None or value < 0 for value in values) or unit_price == 0 or blocked > held:
        return 0
    if any(type(value) is not int or value < 0 for value in (lot, visible, broker_max)) or lot == 0:
        return 0
    gap = max(Decimal(0), current - target)
    return min(1_000_000, visible, broker_max,
               int((gap / (unit_price * lot)).to_integral_value(rounding=ROUND_FLOOR)),
               int(((held - blocked) / lot).to_integral_value(rounding=ROUND_FLOOR)))


def assess_reduction(user, item, account, active, snapshot, target, base):
    uid, kind = item["uid"], item["instrument_type"]
    rows = [row for row in snapshot.get("positions", []) if row.get("account_id") == account and row.get("instrument_uid") == uid]
    if len(rows) != 1 or rows[0].get("blocked"):
        raise HTTPException(409, "sell_position_or_blocked_units_unknown")
    held, blocked = decimal(rows[0].get("quantity")), decimal(rows[0].get("blocked_quantity"))
    started = datetime.now(timezone.utc)
    revision = purchases.research_store.revision(purchases.backend.connect)
    with details.BrokerReader(user) as reader:
        reader.account(account)
        meta = market.broker_read(reader, kind + "_by", {"idType": "INSTRUMENT_ID_TYPE_UID", "id": uid}).get("instrument")
        if not isinstance(meta, dict) or meta.get("uid") != uid or meta.get("sellAvailableFlag") is not True or meta.get("apiTradeAvailableFlag") is not True:
            raise HTTPException(409, "broker_sale_unavailable")
        meta = {**meta, "instrumentType": kind}
        book = market.broker_read(reader, "order_book", {"instrumentId": uid, "depth": 1})
        trading = market.broker_read(reader, "trading_status", {"instrumentId": uid})
        if book.get("instrumentUid") != uid or trading.get("instrumentUid") != uid or not purchases.policy.fresh(book.get("orderbookTs"), started, 60):
            raise HTTPException(409, "order_book_stale_or_undated")
        if book.get("isConsistent", True) is not True or trading.get("limitOrderAvailableFlag") is not True:
            raise HTTPException(409, "limit_trading_unavailable")
        bids = book.get("bids") or []
        if not bids:
            raise HTTPException(409, "order_book_invalid")
        price, visible = decimal(bids[0].get("price")), decimal(bids[0].get("quantity"))
        if price is None or price <= 0 or visible is None or visible < 1 or visible % 1:
            raise HTTPException(409, "order_book_invalid")
        point = purchases.price_quotation(text_number(price))
        unit = decimal(purchases.settlement_price(meta, point))
        query = {"accountId": account, "instrumentId": uid, "price": purchases.settlement_price(meta, point)}
        maximum = market.broker_read(reader, "max_lots", query)
        bound = decimal((maximum.get("sellLimits") or {}).get("sellMaxLots"))
        if bound is None or bound < 0 or bound % 1:
            raise HTTPException(409, "sell_capacity_unknown")
        lots = reduction_lots(decimal(rows[0].get("value")), target, held, blocked, unit, base["lot"], int(visible), int(bound))
        if lots == 0:
            base["missing_evidence"] = ["no_whole_lot_reduction"]
            return base
        quote = market.broker_read(reader, "order_price", {**query, "direction": "ORDER_DIRECTION_SELL", "quantity": str(lots)})
    net = decimal(quote.get("totalOrderAmount"))
    if net is None or net <= 0 or decimal(quote.get("lotsRequested")) != lots or str((quote.get("totalOrderAmount") or {}).get("currency")).upper() != "RUB" or not purchases.quoted_principal_matches(meta, point, quote, lots):
        raise HTTPException(409, "broker_sale_quote_invalid")
    now = datetime.now(timezone.utc)
    base.update(action="sell", suggested_lots=lots, lots_checked=lots, quantity=str(lots * base["lot"]),
        constraints_passed=True, as_of=now.isoformat(), expires_at=purchases.observation_expiry(started, snapshot, book, now).isoformat(),
        total_cost=money(net, "RUB"), evidence_revision=asdict(revision), limit_price=text_number(price),
        explanation="Сокращение превышенной доли. Деньги от продажи учитываются только после подтверждённого поступления.",
        limitations=["tax_and_settlement_effects"], missing_evidence=[])
    purchases.archive_check(user, base, {"snapshot": snapshot}, persist=False)
    return base
