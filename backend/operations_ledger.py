"""Durable observed broker cash movements, not performance or tax accounting.

Called inside the snapshot transaction. No network, connection, commit, order,
balance mutation or guessed zero. Source observation time orders revisions;
the date of an operation does not say when its latest status became known.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Context, Decimal, InvalidOperation, localcontext
import hashlib
import json
import re


class LedgerError(ValueError):
    pass


def _time(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError
        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError, OverflowError):
        raise LedgerError("operation_time_invalid") from None


def _id(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 200
            or value != value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise LedgerError("operation_identity_invalid")
    return value


def _json(value):
    try:
        result = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError, RecursionError):
        raise LedgerError("operation_payload_invalid") from None
    if len(result.encode("utf-8")) > 32768:
        raise LedgerError("operation_payload_too_large")
    return result


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def initialize_in(db):
    """DDL participates in the caller's transaction; never use executescript."""
    if not db.in_transaction:
        raise LedgerError("operation_ledger_transaction_required")
    db.execute("""CREATE TABLE IF NOT EXISTS broker_operation_history_v1 (
        id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, broker_key TEXT NOT NULL,
        account_id TEXT NOT NULL, operation_id TEXT NOT NULL, data_sha256 TEXT NOT NULL,
        observed_at TEXT NOT NULL, received_at TEXT NOT NULL, disposition TEXT NOT NULL,
        reason TEXT, currency TEXT, amount TEXT, bucket TEXT, payload TEXT NOT NULL,
        evidence TEXT NOT NULL)""")
    db.execute("""CREATE INDEX IF NOT EXISTS broker_operation_history_scope
        ON broker_operation_history_v1(user_id,broker_key,account_id,operation_id,observed_at)""")
    db.execute("""CREATE TABLE IF NOT EXISTS broker_operation_current_v1 (
        user_id INTEGER NOT NULL, broker_key TEXT NOT NULL, account_id TEXT NOT NULL,
        operation_id TEXT NOT NULL, observed_at TEXT NOT NULL, history_id TEXT,
        disposition TEXT NOT NULL, reason TEXT,
        PRIMARY KEY(user_id,broker_key,account_id,operation_id))""")
    fields = {row[1] for row in db.execute("PRAGMA table_info(broker_operation_current_v1)")}
    added = False
    for name, default in (("evidence", "[]"), ("received_at", "")):
        if name not in fields:
            db.execute("ALTER TABLE broker_operation_current_v1 ADD COLUMN " + name + " TEXT NOT NULL DEFAULT '" + default + "'")
            added = True
    if added:
        db.execute("UPDATE broker_operation_current_v1 SET evidence=COALESCE((SELECT evidence FROM broker_operation_history_v1 h "
            "WHERE h.id=broker_operation_current_v1.history_id),'[]'), received_at=COALESCE((SELECT received_at "
            "FROM broker_operation_history_v1 h WHERE h.id=broker_operation_current_v1.history_id),'')")
    db.execute("""CREATE TABLE IF NOT EXISTS broker_operation_windows_v1 (
        id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, broker_key TEXT NOT NULL,
        account_id TEXT NOT NULL, range_start TEXT, range_end TEXT,
        observed_at TEXT NOT NULL, received_at TEXT NOT NULL, pagination_complete INTEGER NOT NULL,
        records_valid INTEGER NOT NULL, issues TEXT NOT NULL)""")


def _payment(value):
    if not isinstance(value, dict) or not isinstance(value.get("currency"), str):
        raise LedgerError("operation_payment_missing")
    currency = value["currency"].upper()
    if re.fullmatch(r"[A-Z]{3}", currency) is None:
        raise LedgerError("operation_payment_currency_invalid")
    raw = value.get("value", value.get("amount"))
    try:
        with localcontext(Context(prec=50)):
            if isinstance(raw, dict):
                units, nano = raw.get("units"), raw.get("nano")
                if (isinstance(units, bool) or not isinstance(units, (str, int))
                        or re.fullmatch(r"-?\d{1,25}", str(units)) is None
                        or type(nano) is not int or not -999999999 <= nano <= 999999999
                        or int(units) > 0 > nano or int(units) < 0 < nano):
                    raise LedgerError("operation_payment_invalid")
                amount = Decimal(units) + Decimal(nano) / Decimal(1000000000)
            else:
                if not isinstance(raw, str) or len(raw) > 80:
                    raise LedgerError("operation_payment_invalid")
                amount = Decimal(raw)
            if not amount.is_finite() or amount.copy_abs() > Decimal("1e24") or not -9 <= amount.as_tuple().exponent <= 24:
                raise LedgerError("operation_payment_invalid")
            return currency, format(amount, "f")
    except (InvalidOperation, ValueError, TypeError):
        raise LedgerError("operation_payment_invalid") from None


def _bucket(kind):
    if not isinstance(kind, str) or not kind.startswith("OPERATION_TYPE_"):
        return None
    suffix = kind.removeprefix("OPERATION_TYPE_")
    if suffix == "COUPON":
        return "coupon_income"
    if suffix in {"DIVIDEND", "DIV_EXT"}:
        return "dividend_income"
    if suffix in {"BOND_REPAYMENT", "BOND_REPAYMENT_FULL", "DFA_REDEMPTION"}:
        return "principal_repayment"
    if suffix in {"INPUT", "INPUT_SWIFT", "INPUT_ACQUIRING", "INP_MULTI"}:
        return "external_deposit"
    if suffix in {"OUTPUT", "OUTPUT_SWIFT", "OUTPUT_ACQUIRING", "OUT_MULTI"}:
        return "external_withdrawal"
    if suffix in {"BUY", "SELL", "BUY_CARD", "BUY_MARGIN", "SELL_MARGIN", "DELIVERY_BUY", "DELIVERY_SELL"}:
        return "trade_cash"
    if "TAX" in suffix:
        return "observed_tax_cash"
    if "FEE" in suffix or suffix in {"OVER_COM", "OUT_STAMP_DUTY"}:
        return "fee_cash"
    return None


def _observation(item, refs, fallback, received):
    candidates, evidence = [], []
    identifiers = item.get("source_ids", [])
    if not isinstance(identifiers, list) or any(not isinstance(value, str) for value in identifiers):
        raise LedgerError("operation_source_ids_invalid")
    for source_id in identifiers:
        ref = refs.get(source_id)
        if ref and ref.get("method") == "GetOperationsByCursor" and ref.get("subject_id") == item["account_id"]:
            at = _time(ref.get("observed_at"))
            if at > received:
                raise LedgerError("operation_source_from_future")
            candidates.append(at)
            evidence.append(source_id)
    if candidates:
        return max(candidates).isoformat(), sorted(set(evidence)), None
    return fallback or "", [], "operation_observation_source_missing"


def _history_in(db, scope, observed, received, disposition, reason, currency, amount, bucket, encoded, data_sha, evidence):
    history_id = _hash([*scope, observed, data_sha, evidence, disposition, reason])
    db.execute("INSERT OR IGNORE INTO broker_operation_history_v1 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (history_id, *scope, data_sha, observed, received, disposition, reason, currency, amount, bucket, encoded, _json(evidence)))
    return history_id


def _current_in(db, scope):
    row = db.execute("SELECT c.observed_at,c.history_id,c.disposition,c.reason,c.evidence,c.received_at,"
        "h.data_sha256,h.observed_at,h.currency,h.amount,h.bucket,h.payload "
        "FROM broker_operation_current_v1 c LEFT JOIN broker_operation_history_v1 h ON h.id=c.history_id "
        "WHERE c.user_id=? AND c.broker_key=? AND c.account_id=? AND c.operation_id=?", scope).fetchone()
    names = ("observed_at", "history_id", "disposition", "reason", "evidence", "received_at", "data_sha256",
        "first_observed_at", "currency", "amount", "bucket", "payload")
    return dict(zip(names, row)) if row else None


def _record_in(db, scope, item, refs, fallback, received, bounds):
    payload = {key: value for key, value in item.items() if key not in {"source_ids", "position_ref"}}
    encoded, data_sha = _json(payload), _hash(payload)
    reason, currency, amount, bucket = None, None, None, _bucket(item.get("type"))
    try:
        observed, evidence, reason = _observation(item, refs, fallback, received)
    except LedgerError as error:
        observed, evidence, reason = fallback or "", [], str(error)
    status = item.get("state")
    disposition = "pending" if status == "OPERATION_STATE_PROGRESS" else "cancelled" if status == "OPERATION_STATE_CANCELED" else "accepted"
    try:
        when = _time(item.get("date"))
        if observed and when > _time(observed):
            raise LedgerError("operation_date_after_observation")
        if bounds is None or not bounds[0] <= when <= bounds[1]:
            raise LedgerError("operation_outside_observed_range")
        if status not in {"OPERATION_STATE_EXECUTED", "OPERATION_STATE_PROGRESS", "OPERATION_STATE_CANCELED"}:
            raise LedgerError("operation_state_unknown")
        if status == "OPERATION_STATE_EXECUTED":
            currency, amount = _payment(item.get("payment"))
            if bucket is None:
                raise LedgerError("operation_type_unclassified")
    except LedgerError as error:
        reason = str(error)
    if reason:
        disposition, currency, amount = "quarantined", None, None
    current = _current_in(db, scope) if observed else None
    signature = (data_sha, disposition, reason)
    same = current is not None and signature == (current["data_sha256"], current["disposition"], current["reason"])
    if same and observed >= current["observed_at"]:
        # A repeated attestation updates current provenance, not immutable
        # payload history. It does not claim continuous observation in between.
        if observed == current["observed_at"]:
            evidence = sorted(set(evidence) | set(json.loads(current["evidence"])))
        db.execute("UPDATE broker_operation_current_v1 SET observed_at=?,evidence=?,received_at=? "
            "WHERE user_id=? AND broker_key=? AND account_id=? AND operation_id=?",
            (observed, _json(evidence), received.isoformat(), *scope))
        return disposition == "quarantined"
    if (current and current["history_id"] and not same
            and current["first_observed_at"] < current["observed_at"]):
        # Preserve the last confirmed state before any different observation.
        # A later-arriving intermediate change can require this witness even
        # after a newer version has replaced current.
        witness = _history_in(db, scope, current["observed_at"], current["received_at"],
            current["disposition"], current["reason"], current["currency"], current["amount"], current["bucket"],
            current["payload"], current["data_sha256"], json.loads(current["evidence"]))
        if observed < current["observed_at"]:
            db.execute("UPDATE broker_operation_current_v1 SET history_id=? "
                "WHERE user_id=? AND broker_key=? AND account_id=? AND operation_id=?", (witness, *scope))
    history_id = _history_in(db, scope, observed, received.isoformat(), disposition, reason,
        currency, amount, bucket, encoded, data_sha, evidence)
    if not observed:
        return True  # Unknown observation time cannot replace a known current state.
    if current is None or observed > current["observed_at"]:
        db.execute("INSERT INTO broker_operation_current_v1(user_id,broker_key,account_id,operation_id,observed_at,"
            "history_id,disposition,reason,evidence,received_at) VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(user_id,broker_key,account_id,operation_id) DO UPDATE SET observed_at=excluded.observed_at, "
            "history_id=excluded.history_id,disposition=excluded.disposition,reason=excluded.reason,"
            "evidence=excluded.evidence,received_at=excluded.received_at",
            (*scope, observed, history_id, disposition, reason, _json(evidence), received.isoformat()))
    conflicted = False
    if current is not None and observed == current["observed_at"]:
        versions = db.execute("SELECT DISTINCT data_sha256,disposition,reason FROM broker_operation_history_v1 "
            "WHERE user_id=? AND broker_key=? AND account_id=? AND operation_id=? AND observed_at=?", (*scope, observed)).fetchall()
        if len(versions) > 1:
            conflicted = True
            db.execute("UPDATE broker_operation_current_v1 SET history_id=NULL,disposition='conflicted',reason='operation_same_time_conflict' "
                "WHERE user_id=? AND broker_key=? AND account_id=? AND operation_id=?", scope)
    return disposition == "quarantined" or conflicted


def record_snapshot_in(db, *, user_id: int, broker_key: str, snapshot: dict, at: datetime | None = None) -> dict:
    """Append observations and return a materialized receipt, atomically with snapshot."""
    initialize_in(db)
    if type(user_id) is not int or user_id <= 0:
        raise LedgerError("operation_user_invalid")
    _id(broker_key)
    received = datetime.now(timezone.utc) if at is None else _time(at.isoformat())
    accounts = sorted({_id(row["id"]) for row in snapshot.get("accounts", [])})
    operations = snapshot.get("operations")
    if not isinstance(operations, dict):
        return {"state": "unavailable", "reason": "operations_not_collected", "history_preserved": True}
    refs = {row["id"]: row for row in snapshot.get("sources", []) if isinstance(row, dict) and isinstance(row.get("id"), str)}
    try:
        fallback_time = _time(snapshot.get("section_as_of", {}).get("operations"))
        fallback = fallback_time.isoformat() if fallback_time <= received else None
    except (LedgerError, AttributeError):
        fallback = None
    issues, invalid_accounts = defaultdict(list), []
    try:
        begin, finish = _time(operations.get("start")), _time(operations.get("end"))
        if not begin < finish <= received:
            raise LedgerError("operation_range_invalid")
        range_valid = True
    except LedgerError:
        begin = finish = None
        range_valid = False
    rows = operations.get("items")
    if not isinstance(rows, list):
        rows, invalid_accounts = [], ["operation_items_invalid"]
    for item in rows:
        account = item.get("account_id") if isinstance(item, dict) else None
        try:
            if account not in accounts:
                raise LedgerError("operation_account_not_in_snapshot")
            operation_id = _id(item.get("id"))
            invalid = _record_in(db, (user_id, broker_key, account, operation_id), item, refs, fallback, received,
                (begin, finish) if range_valid else None)
            if invalid:
                issues[account].append("quarantined_operation")
        except LedgerError as error:
            (issues[account] if account in accounts else invalid_accounts).append(str(error))
    for account in accounts:
        account_issues = sorted(set(issues[account] + invalid_accounts + ([] if range_valid else ["operation_range_invalid"])))
        if operations.get("complete") is not True:
            account_issues.append("operation_pagination_incomplete")
        observed_times = []
        for ref in refs.values():
            if ref.get("method") != "GetOperationsByCursor" or ref.get("subject_id") != account:
                continue
            try:
                observed = _time(ref.get("observed_at"))
                if observed > received:
                    raise LedgerError("operation_source_range_time_invalid")
                if finish is not None and observed < finish:
                    continue  # Retained attribution provenance does not describe this newer window.
                observed_times.append(observed)
            except LedgerError:
                account_issues.append("operation_source_range_time_invalid")
        if not observed_times:
            account_issues.append("operation_account_observation_missing")
        observed = max(observed_times).isoformat() if observed_times else fallback or ""
        account_issues = sorted(set(account_issues))
        payload = [user_id, broker_key, account, begin.isoformat() if begin else None,
            finish.isoformat() if finish else None, observed, received.isoformat(), operations.get("complete") is True,
            not account_issues, account_issues]
        db.execute("INSERT OR IGNORE INTO broker_operation_windows_v1 VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (_hash(payload[:6] + payload[7:]), *payload[:-1], _json(account_issues)))
    return summary_in(db, user_id=user_id, broker_key=broker_key, account_ids=accounts)


def summary_in(db, *, user_id: int, broker_key: str, account_ids: list[str]) -> dict:
    totals, counts, coverage = defaultdict(Decimal), defaultdict(int), []
    with localcontext(Context(prec=50)):
        for account in account_ids:
            rows = db.execute("SELECT c.disposition,h.currency,h.amount,h.bucket FROM broker_operation_current_v1 c "
                "LEFT JOIN broker_operation_history_v1 h ON h.id=c.history_id "
                "WHERE c.user_id=? AND c.broker_key=? AND c.account_id=?", (user_id, broker_key, account))
            for disposition, currency, amount, bucket in rows:
                counts[disposition] += 1
                if disposition == "accepted":
                    totals[currency, bucket] += Decimal(amount)
            windows = db.execute("SELECT range_start,range_end,observed_at,received_at,pagination_complete,records_valid,issues FROM broker_operation_windows_v1 "
                "WHERE user_id=? AND broker_key=? AND account_id=? ORDER BY observed_at DESC,id DESC", (user_id, broker_key, account)).fetchall()
            complete_ranges = sorted({(row[0], row[1]) for row in windows if row[0] and row[1] and row[4] and row[5]})
            merged = []
            for begin, end in complete_ranges:
                if merged and begin <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], end)
                else:
                    merged.append([begin, end])
            latest_time = max((row[2] for row in windows), default="")
            latest = [row for row in windows if row[2] == latest_time or not row[2] and row[3] >= latest_time]
            coverage.append({"account_id": account, "complete_observed_ranges": merged,
                "known_gaps": [[left[1], right[0]] for left, right in zip(merged, merged[1:])],
                "latest_observation_complete": bool(latest) and all(row[2] and row[4] and row[5] for row in latest),
                "latest_observed_at": latest_time or None,
                "latest_issues": sorted({issue for row in latest for issue in json.loads(row[6])}) if latest else ["no_observed_range"],
                "outside_observed_ranges_unknown": True})
    valid = not counts["quarantined"] and not counts["conflicted"] and all(row["latest_observation_complete"] and not row["known_gaps"] for row in coverage)
    return {"state": "observed" if valid and coverage else "partial", "operation_counts": dict(counts),
        "cash_movements": [{"currency": currency, "category": bucket, "amount": format(amount, "f")}
            for (currency, bucket), amount in sorted(totals.items())], "coverage": coverage,
        "history_preserved": True, "scope": "current_broker_connection_and_snapshot_accounts",
        "cash_basis": "executed_operation_payment_only", "commission_annotations_added": False,
        "income_categories": ["coupon_income", "dividend_income"],
        "principal_repayments_are_income": False, "performance_calculated": False, "tax_liability_estimated": False}
