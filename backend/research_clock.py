"""Time boundaries for the existing research cache, not a second result cache.

An unchanged database revision does not mean an unchanged assessment: sources
expire, embargoed imports become available, and news/history age out. A bounded
registry retains only the next known boundary for a cache identity. Result data
and single-flight loading stay in portfolio_details.cached. No broker/LLM calls.
"""
from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from itertools import count
from threading import RLock

TTL_SECONDS = 300
MAX_WINDOWS = 256
_ACTIVE: ContextVar[ResearchWindow | None] = ContextVar('research_read_window', default=None)
_LOCK = RLock()
_SERIALS = count()
_WINDOWS: OrderedDict[tuple, ResearchWindow] = OrderedDict()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(at: datetime) -> datetime:
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise ValueError('research_clock_timezone_required')
    return at.astimezone(timezone.utc)


class ResearchWindow:
    def __init__(self, serial: int, at: datetime):
        self.serial = serial
        self.started_at = _aware(at)
        self.deadline = self.started_at + timedelta(seconds=TTL_SECONDS)
        self._lock = RLock()

    def current(self, at: datetime | None = None) -> bool:
        instant = _aware(utc_now() if at is None else at)
        with self._lock:
            return self.started_at <= instant < self.deadline

    def note(self, at: datetime) -> None:
        instant = _aware(at)
        with self._lock:
            if self.started_at < instant < self.deadline:
                self.deadline = instant

    @contextmanager
    def observing(self):
        token = _ACTIVE.set(self)
        try:
            yield self
        finally:
            _ACTIVE.reset(token)


def window_for(key: tuple, *, at: datetime | None = None) -> ResearchWindow:
    instant = _aware(utc_now() if at is None else at)
    with _LOCK:
        window = _WINDOWS.get(key)
        if window is None or not window.current(instant):
            window = ResearchWindow(next(_SERIALS), instant)
            _WINDOWS[key] = window
        _WINDOWS.move_to_end(key)
        while len(_WINDOWS) > MAX_WINDOWS:
            _WINDOWS.popitem(last=False)
        return window


def note_time(value: datetime | str | None) -> None:
    window = _ACTIVE.get()
    if window is None:
        return
    try:
        if isinstance(value, str):
            if len(value) > 64:
                return
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        window.note(value)
    except (ValueError, TypeError, OverflowError):
        # This observer never validates evidence. Existing selectors still
        # reject malformed times; passage of time cannot repair such a value.
        return


def note_source(source: dict) -> None:
    for name in ('published_at', 'checked_at', 'expires_at'):
        note_time(source.get(name))
