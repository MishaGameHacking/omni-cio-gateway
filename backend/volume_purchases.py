"""Read-only pre-trade checks bound to owned accounts, strategy and evidence versions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import asdict
from contextlib import closing
import json
import uuid
from typing import Annotated, Any

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

try:
    from . import app as backend, portfolio_details as details, research_store
    from . import volume_market as market, volume_state as state, purchase_policy as policy
    from .credit_evidence import Rating, Source, credit_assessment
    from .ai_budget import transaction
    from .volume_contract import HTTP_ERRORS, decimal, digest, text_number, financial_context, timestamp
except ImportError:
    import app as backend
    import portfolio_details as details
    import research_store
    import volume_market as market
    import volume_state as state
    import purchase_policy as policy
    from credit_evidence import Rating, Source, credit_assessment
    from ai_budget import transaction
    from volume_contract import HTTP_ERRORS, decimal, digest, text_number, financial_context, timestamp

router = APIRouter(prefix="/workspace/purchases", tags=["Personal purchase constraint checks"])


class PurchaseCheck(state.StrictModel):
    account_id: str = Field(min_length=1, max_length=160)
    instrument_uid: str = Field(min_length=1, max_length=160)
    lots: int = Field(ge=1, le=1_000_000, strict=True)
    limit_price: str = Field(min_length=1, max_length=40)
    strategy_version: int = Field(ge=1, strict=True)


@financial_context
def price_quotation(value: str) -> dict:
    amount = decimal(value)
    if amount is None or not 0 < amount <= 1_000_000_000_000 or amount * 1_000_000_000 % 1:
        raise HTTPException(422, "purchase_limit_price_invalid")
    units = int(amount)
    return {"units": str(units), "nano": int((amount - units) * 1_000_000_000)}


@financial_context
def settlement_price(meta: dict, points: dict) -> dict:
    if meta.get("instrumentType") != "bond":
        return points
    nominal = meta.get("nominal")
    amount = decimal(nominal)
    if (not isinstance(nominal, dict) or amount is None or amount <= 0
            or str(nominal.get("currency", "")).upper() != str(meta.get("currency", "")).upper()):
        raise HTTPException(409, "bond_nominal_currency_conversion_unverified")
    return price_quotation(text_number(decimal(points) * amount / 100))


@financial_context
def quoted_principal_matches(meta: dict, points: dict, quote: dict, lots: int) -> bool:
    lot, initial = decimal(meta.get("lot")), decimal(quote.get("initialOrderAmount"))
    if lot is None or lot <= 0 or initial is None:
        return False
    expected = decimal(settlement_price(meta, points)) * lot * lots
    # Broker monetary rounding is bounded to one minor unit for supported
    # RUB/USD/EUR strategies. A percent/nominal mix-up cannot pass this check.
    return abs(expected - initial) <= decimal("0.01")


def reviewed_credit(uid: str, kind: str, now: datetime) -> tuple[dict, dict]:
    try:
        return _reviewed_credit(uid, kind, now)
    except (ValueError, TypeError, KeyError):
        raise HTTPException(503, "purchase_credit_evidence_unavailable") from None


def _reviewed_credit(uid: str, kind: str, now: datetime) -> tuple[dict, dict]:
    identity = research_store.latest_verified(backend.connect, "issuer_identity", uid, now) or {}
    issuer = identity.get("issuer_id")
    records = research_store.records(backend.connect, "rating", uid, at=now)
    if issuer:
        records += research_store.records(backend.connect, "rating", issuer, at=now)
    ratings = [Rating(**{**row, "source": Source(**row["source"])}) for row in records]
    return identity, credit_assessment(ratings, issuer_id=issuer, instrument_id=uid, at=now, bond=kind == "bond")


def _broker_observations(user, payload, price):
    with details.BrokerReader(user) as reader:
        reader.account(payload.account_id)  # Ownership before any account-specific read.
        meta = reader.read("instrument", {"idType": "INSTRUMENT_ID_TYPE_UID", "id": payload.instrument_uid}).get("instrument")
        if not isinstance(meta, dict) or meta.get("uid") != payload.instrument_uid:
            raise HTTPException(502, "instrument_identity_mismatch")
        kind = market.instrument_kind(meta)
        if kind not in {"share", "bond", "etf"}:
            raise HTTPException(422, "instrument_requires_separate_risk_model")
        # GetInstrumentBy omits bond-specific risk flags. A typed observation is
        # mandatory; never interpret missing subordinate/perpetual flags as false.
        full = market.broker_read(reader, kind + "_by", {"idType": "INSTRUMENT_ID_TYPE_UID", "id": payload.instrument_uid}).get("instrument")
        if not isinstance(full, dict) or full.get("uid") != payload.instrument_uid:
            raise HTTPException(502, "instrument_identity_mismatch")
        meta = {**full, "instrumentType": kind}
        if kind == "bond":
            # Proto3 omits default false booleans; this is safe only after the
            # typed BondBy response, not a generic Instrument response.
            for flag in ("subordinatedFlag", "perpetualFlag"):
                meta[flag] = full.get(flag, False)
        if kind == "etf":
            asset = market.broker_read(reader, "asset", {"id": meta.get("assetUid")}).get("asset")
            if not isinstance(asset, dict) or asset.get("uid") != meta.get("assetUid"):
                raise HTTPException(502, "fund_asset_identity_mismatch")
            security = asset.get("security") or {}
            if security.get("type") != "etf" or not isinstance(security.get("etf"), dict):
                raise HTTPException(502, "fund_terms_unverified")
            meta["fund_policy"] = {"asset_uid": asset["uid"], "details": security["etf"]}
        info = market.broker_read(reader, "user_info", {})
        query = {"accountId": payload.account_id, "instrumentId": payload.instrument_uid,
                 "price": settlement_price(meta, price)}
        limits = market.broker_read(reader, "max_lots", query)
        quote = market.broker_read(reader, "order_price", {**query, "direction": "ORDER_DIRECTION_BUY", "quantity": str(payload.lots)})
        trading = market.broker_read(reader, "trading_status", {"instrumentId": payload.instrument_uid})
        book = market.broker_read(reader, "order_book", {"instrumentId": payload.instrument_uid, "depth": 50})
        for observed in (book, trading):
            if observed.get("instrumentUid") != payload.instrument_uid:
                raise HTTPException(502, "purchase_market_identity_mismatch")
    return meta, info, limits, quote, trading, book


@financial_context
def liquidity_reasons(book: dict, trading: dict, price: str, lots: int, now: datetime) -> list[str]:
    reasons = []
    if trading.get("limitOrderAvailableFlag") is not True or trading.get("apiTradeAvailableFlag") is not True:
        reasons.append("limit_trading_unavailable")
    if not policy.fresh(book.get("orderbookTs"), now, 60):
        reasons.append("order_book_stale_or_undated")
    # This is unary GetOrderBookResponse; isConsistent belongs to the stream.
    # Missing is expected, while an explicitly adverse/malformed flag still blocks.
    if "isConsistent" in book and book["isConsistent"] is not True:
        reasons.append("order_book_not_consistent")
    rows, available = book.get("asks"), 0
    if not isinstance(rows, list):
        return reasons + ["order_book_invalid"]
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            return reasons + ["order_book_invalid"]
        value, quantity = decimal(row.get("price")), decimal(row.get("quantity"))
        if value is None or value <= 0 or quantity is None or quantity < 0 or quantity % 1 or value in seen:
            return reasons + ["order_book_invalid"]
        seen.add(value)
        if value <= decimal(price):
            available += int(quantity)
    if available < lots:
        reasons.append("insufficient_visible_liquidity_at_limit")
    return reasons


def archive_check(user, result: dict, inputs: dict, *, persist: bool = True) -> str | None:
    """Validate current inputs; archive immutable evidence for interactive checks."""
    user_id = int(user["id"])
    identifier = uuid.uuid4().hex if persist else None
    with transaction(backend.connect) as db:
        if result["constraints_passed"] and timestamp(result["expires_at"]) <= datetime.now(timezone.utc):
            raise HTTPException(409, "purchase_observations_expired")
        active = state.active_strategy(user_id, db)
        saved = db.execute("SELECT id,broker_key FROM workspace_snapshots WHERE user_id=? AND currency=?",
                           (user_id, inputs["snapshot"]["currency"])).fetchone()
        owner = db.execute("SELECT tinvest_token_encrypted FROM users WHERE id=?", (user_id,)).fetchone()
        if (not active or active["version"] != result["strategy_version"] or not saved
                or saved["id"] != result["snapshot_id"] or not owner
                or state.broker_key(owner) != state.broker_key(user)
                or saved["broker_key"] != state.broker_key(user)
                or asdict(research_store.read_revision(db)) != result["evidence_revision"]):
            raise HTTPException(409, "purchase_inputs_changed")
        result["check_id"] = identifier
        if persist:
            encrypted = backend.FERNET.encrypt(state.encode({"result": result, "inputs": inputs}).encode()).decode()
            state.record(db, user_id, "purchase_check", identifier, {"encrypted": encrypted})
    return identifier


def observation_expiry(started, snapshot, book, now):
    """A later calculation must not renew the lifetime of older observations."""
    deadlines = [started + timedelta(seconds=60)]
    for value, lifetime in ((snapshot.get("as_of"), 300), (book.get("orderbookTs"), 60)):
        try:
            observed = timestamp(value)
            deadlines.append(observed + timedelta(seconds=lifetime) if observed <= now else now)
        except ValueError:
            deadlines.append(now)
    return min(deadlines)


@router.get("/checks/{identifier}", responses=HTTP_ERRORS)
def historical_check(identifier: str, user: Annotated[Any, Depends(backend.current_user)]) -> dict:
    with closing(backend.connect()) as db:
        row = db.execute("SELECT payload_json FROM workspace_records WHERE user_id=? AND kind='purchase_check' AND id=?",
                         (int(user["id"]), identifier)).fetchone()
    if row is None:
        raise HTTPException(404, "purchase_check_not_found")
    try:
        archived = json.loads(backend.FERNET.decrypt(json.loads(row[0])["encrypted"].encode()))
    except (InvalidToken, ValueError, KeyError, TypeError):
        raise HTTPException(500, "purchase_check_unreadable") from None
    # Historical evidence is never an authorization to act on a current account.
    return {**archived, "historical_only": True, "requires_new_check": True}


@router.post("/check", responses=HTTP_ERRORS)
def check_purchase(payload: PurchaseCheck, user: Annotated[Any, Depends(backend.current_user)]) -> dict:
    return _check_purchase(payload, user)


@financial_context
def _check_purchase(payload: PurchaseCheck, user: Any, *, archive: bool = True) -> dict:
    price = price_quotation(payload.limit_price)
    active = state.active_strategy(int(user["id"]))
    if not active or active["version"] != payload.strategy_version:
        raise HTTPException(409, "confirmed_strategy_required_or_changed")
    config = active["config"]
    snapshot = state.saved_snapshot(user, config["reserve"]["currency"])
    if not snapshot or not policy.fresh(snapshot.get("as_of"), datetime.now(timezone.utc), 300):
        raise HTTPException(409, "purchase_fresh_snapshot_required")
    revision = research_store.revision(backend.connect)
    started = datetime.now(timezone.utc)
    meta, info, limits, quote, trading, book = _broker_observations(user, payload, price)
    now = datetime.now(timezone.utc)
    identity, credit = reviewed_credit(payload.instrument_uid, meta.get("instrumentType"), now)
    result = policy.assess_purchase(snapshot=snapshot, config=config, meta=meta, identity=identity,
        credit=credit, info=info, quote=quote, capacity=limits, lots=payload.lots,
        account_id=payload.account_id, observed_at=started.isoformat(), now=now)
    reasons = result["reasons"] + liquidity_reasons(book, trading, payload.limit_price, payload.lots, now)
    if not quoted_principal_matches(meta, price, quote, payload.lots):
        reasons.append("broker_price_unit_or_principal_mismatch")
    step = decimal(meta.get("minPriceIncrement"))
    if step is None or step <= 0 or decimal(payload.limit_price) % step:
        reasons.append("price_step_unverified_or_invalid")
    current = state.active_strategy(int(user["id"]))
    latest = state.saved_snapshot(user, config["reserve"]["currency"])
    if not current or current["version"] != active["version"] or not latest or latest["snapshot_id"] != snapshot["snapshot_id"] or research_store.revision(backend.connect) != revision:
        raise HTTPException(409, "purchase_inputs_changed")
    result.update(reasons=sorted(set(reasons)), constraints_passed=not reasons,
        instrument_uid=payload.instrument_uid, account_id=payload.account_id,
        limit_price=text_number(decimal(payload.limit_price)), as_of=now.isoformat(),
        expires_at=observation_expiry(started, snapshot, book, now).isoformat(), snapshot_id=snapshot["snapshot_id"],
        strategy_version=active["version"], evidence_revision=asdict(revision),
        advice_kind="personalized_purchase_constraint_check",
        investor_qualified=info.get("qualStatus") is True,
        investor_tests=info.get("qualifiedForWorkWith", []),
        suitability_complete=False,
        remaining_checks=["loss_capacity_and_full_investment_profile", "investment_thesis_and_valuation", "tax_and_settlement_effects"],
        explanation="Проверка ограничений конкретной покупки. Полная инвестиционная рекомендация требует оценки способности нести убытки и инвестиционного обоснования.")
    inputs = {"snapshot": snapshot, "strategy": active, "instrument": meta, "broker_user_info": info,
        "identity": identity, "credit": credit, "capacity": limits, "quote": quote, "book": book,
        "trading": trading, "request": payload.model_dump(), "observed_at": now.isoformat(),
        "broker_read_started_at": started.isoformat(), "policy": policy.POLICY_VERSION}
    result["input_digest"] = digest(inputs)
    if archive:
        archive_check(user, result, inputs)
    else:
        # Automatic catalogue research persists a bounded compact summary, not
        # hundreds of duplicated full account archives every day. The same
        # transactional input/expiry checks still run before returning.
        archive_check(user, result, inputs, persist=False)
    return result

