"""Aggregate one broker snapshot without guessing missing identity or valuation.

Pure, read-only preparation shared by research and its regression tests. A UID is
required: two unidentifiable holdings must never collapse into one None key.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

ZERO = Decimal(0)
IDENTITY_FIELDS = ('instrumentType', 'assetUid', 'isin', 'classCode', 'ticker')


class SnapshotError(ValueError):
    """The broker snapshot cannot support a coherent portfolio assessment."""


def _rows(value: object) -> list[dict]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise SnapshotError('invalid_snapshot_rows')
    return value


def _identity(raw: dict) -> str:
    uid = raw.get('id')
    if not isinstance(uid, str) or not uid.strip() or len(uid) > 160:
        raise SnapshotError('missing_instrument_identity')
    if uid != uid.strip() or any(ord(c) < 32 for c in uid):
        raise SnapshotError('invalid_instrument_identity')
    for field in IDENTITY_FIELDS:
        value = raw.get(field)
        if value is not None and not isinstance(value, str):
            raise SnapshotError('invalid_instrument_metadata')
    return uid


def _merge(previous: dict, raw: dict, value: Decimal | None) -> None:
    for key in IDENTITY_FIELDS:
        before, after = previous.get(key), raw.get(key)
        if before and after and before != after:
            raise SnapshotError('conflicting_instrument_identity')
        if not before and after:
            previous[key] = after
    old = previous['_aggregate_value']
    previous['_aggregate_value'] = old + value if old is not None and value is not None else None
    previous['blocked'] = bool(previous.get('blocked')) or bool(raw.get('blocked'))


@dataclass
class Inventory:
    positions: dict[str, dict] = field(default_factory=dict)
    cash: Decimal = ZERO
    full_cash: bool = True
    complex_valuation: bool = False

    def add(self, raw: dict, value: Decimal | None) -> None:
        if value is not None and (not isinstance(value, Decimal) or not value.is_finite()):
            raise SnapshotError('invalid_position_valuation')
        if raw.get('instrumentType') == 'cash':
            self.full_cash = self.full_cash and value is not None and value >= ZERO
            self.cash += value if value is not None else ZERO
            return
        uid = _identity(raw)
        if uid in self.positions:
            _merge(self.positions[uid], raw, value)
        else:
            self.positions[uid] = {**raw, '_aggregate_value': value}

    def fully_valued(self, values: dict[str, Decimal], total: Decimal) -> bool:
        if not self.full_cash or self.complex_valuation or set(values) != set(self.positions):
            return False
        if total <= ZERO or any(value < ZERO for value in values.values()):
            return False
        return abs(sum(values.values(), ZERO) + self.cash - total) <= Decimal('.02')


def aggregate(snapshot: dict, read_amount: Callable[[dict, str], Decimal | None],
              currency: str) -> Inventory:
    inventory = Inventory()
    for account in _rows(snapshot.get('accounts', [])):
        if account.get('virtualPositions') or account.get('limitsLoading'):
            inventory.complex_valuation = True
        for raw in _rows(account.get('positions', [])):
            inventory.add(raw, read_amount(raw, currency))
    return inventory
