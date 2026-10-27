"""Read-only market adapters and evidence-rich instrument dossiers."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import re
import threading
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

try:
    from . import app as backend, portfolio_details as details, research_store
    from .credit_evidence import Rating, Source, credit_assessment, EvidenceError
    from .investment_links import instrument_link
    from .volume_contract import (HTTP_ERRORS, SCHEMA_VERSION, date_range, decimal, digest,
        error_code, money, now_iso, require_id, safe_section, section, source,
        text_number, timestamp, reviewed_source, financial_context)
except ImportError:
    import app as backend
    import portfolio_details as details
    import research_store
    from credit_evidence import Rating, Source, credit_assessment, EvidenceError
    from investment_links import instrument_link
    from volume_contract import (HTTP_ERRORS, SCHEMA_VERSION, date_range, decimal, digest,
        error_code, money, now_iso, require_id, safe_section, section, source,
        text_number, timestamp, reviewed_source, financial_context)

router = APIRouter(prefix='/workspace', tags=['workspace-market'])
DOCS = 'https://developer.tbank.ru/invest/api/'
READ_METHODS = {
    'candles': 'MarketDataService/GetCandles',
    'trading_status': 'MarketDataService/GetTradingStatus',
    'order_book': 'MarketDataService/GetOrderBook',
    'calendar': 'InstrumentsService/TradingSchedules',
    'reports': 'InstrumentsService/GetAssetReports',
    'fundamentals': 'InstrumentsService/GetAssetFundamentals',
    'news': 'InstrumentsService/News',
    'asset': 'InstrumentsService/GetAssetBy',
    'shares': 'InstrumentsService/Shares', 'bonds': 'InstrumentsService/Bonds',
    'etfs': 'InstrumentsService/Etfs', 'currencies': 'InstrumentsService/Currencies',
    'futures': 'InstrumentsService/Futures', 'options': 'InstrumentsService/Options',
    'user_info': 'UsersService/GetInfo',
    'max_lots': 'OrdersService/GetMaxLots',
    'order_price': 'OrdersService/GetOrderPrice',
    'bond_by': 'InstrumentsService/BondBy',
    'share_by': 'InstrumentsService/ShareBy',
}
_rate_lock = threading.Lock()
_next_instrument_read: dict[tuple, float] = {}


def pace_instruments(scope: tuple) -> None:
    # Leave headroom below the documented 200/minute instrument-service limit.
    # The wait is bounded and is never driven by animation frames.
    with _rate_lock:
        now = time.monotonic()
        due = max(now, _next_instrument_read.get(scope, now))
        if due - now > 5:
            raise HTTPException(429, 'instrument_request_queue_full')
        _next_instrument_read[scope] = due + 0.4
        if len(_next_instrument_read) > 256:
            expired = [key for key, deadline in _next_instrument_read.items() if deadline < now]
            for key in expired:
                del _next_instrument_read[key]
    delay = due - now
    if delay > 0:
        time.sleep(delay)
INTERVALS = {
    'minute': ('CANDLE_INTERVAL_1_MIN', 1, 2400),
    'five_minutes': ('CANDLE_INTERVAL_5_MIN', 7, 2400),
    'quarter_hour': ('CANDLE_INTERVAL_15_MIN', 21, 2400),
    'hour': ('CANDLE_INTERVAL_HOUR', 90, 2400),
    'day': ('CANDLE_INTERVAL_DAY', 2192, 2400),
    'week': ('CANDLE_INTERVAL_WEEK', 1826, 300),
    'month': ('CANDLE_INTERVAL_MONTH', 3652, 120),
}


def broker_read(reader: details.BrokerReader, method: str, body: dict) -> dict:
    if method not in READ_METHODS:
        raise ValueError('read_method_not_allowed')
    if READ_METHODS[method].startswith('InstrumentsService/'):
        pace_instruments(reader.scope)
    return details.portfolio._post_tinvest(reader.client,
        details.BASE + READ_METHODS[method], reader.token, body)


def instrument(user: Any, uid: str) -> dict:
    require_id(uid)
    def load():
        with details.BrokerReader(user) as reader:
            pace_instruments(reader.scope)
            raw = reader.read('instrument', {'idType': 'INSTRUMENT_ID_TYPE_UID', 'id': uid})
        item = raw.get('instrument')
        if not isinstance(item, dict) or item.get('uid') != uid:
            raise HTTPException(502, 'instrument_identity_mismatch')
        item = {**item, '_source': source('GetInstrumentBy', uid, now_iso(),
                url=DOCS + 'instruments-service-get-instrument-by', ttl=86400)}
        return item
    # Full instrument responses contain client-specific requiredTests/rights.
    return details.cached(('workspace-instrument', *details.identity(user), uid), 300, load)


def instrument_kind(raw: dict) -> str:
    return str(raw.get('instrumentType') or raw.get('instrumentKind') or '').lower().removeprefix('instrument_type_')


def quote_unit(raw: dict, price_currency: str | None = None) -> tuple[str, str, str | None]:
    kind = instrument_kind(raw)
    if kind == 'bond':
        return 'percent_of_nominal', '% номинала', None
    if kind in {'future', 'futures'}:
        return 'points', 'пункты', None
    currency = str(price_currency or raw.get('currency') or '').upper()
    if re.fullmatch(r'[A-Z]{3}', currency):
        return 'quote_currency', currency, currency
    return 'quote_units', 'единицы котировки', None


def _normalized_candle(raw: dict, observed_at: str, source_id: str) -> dict:
    if not isinstance(raw, dict):
        raise HTTPException(502, 'candles_invalid_response')
    values = {key: decimal(raw.get(key)) for key in ('open', 'high', 'low', 'close')}
    if any(value is None for value in values.values()):
        raise HTTPException(502, 'candles_invalid_price')
    if not values['low'] <= min(values['open'], values['close']) <= max(values['open'], values['close']) <= values['high']:
        raise HTTPException(502, 'candles_invalid_ohlc')
    try:
        instant = timestamp(raw.get('time'))
        if instant > timestamp(observed_at):
            raise ValueError
    except ValueError:
        raise HTTPException(502, 'candles_invalid_time') from None
    volume = raw.get('volume')
    if isinstance(volume, bool) or not re.fullmatch(r'\d{1,19}', str(volume)):
        raise HTTPException(502, 'candles_invalid_volume')
    complete = raw.get('isComplete')
    if type(complete) is not bool:
        raise HTTPException(502, 'candles_completion_unknown')
    return {'time': instant.isoformat(), **{key: text_number(value) for key, value in values.items()},
            'volume_lots': str(int(volume)), 'is_complete': complete, 'source_id': source_id}


def normalize_candles(rows: Any, *, observed_at: str, source_id: str) -> list[dict]:
    if not isinstance(rows, list):
        raise HTTPException(502, 'candles_invalid_response')
    result = {}
    for raw in rows:
        row = _normalized_candle(raw, observed_at, source_id)
        if row['time'] in result and result[row['time']] != row:
            raise HTTPException(502, 'candles_conflicting_values')
        result[row['time']] = row
    return sorted(result.values(), key=lambda row: row['time'])


def load_candles(user: Any, uid: str, start: date | None, end: date | None, interval: str) -> dict:
    if interval not in INTERVALS:
        raise HTTPException(422, 'candle_interval_not_supported')
    enum, max_days, limit = INTERVALS[interval]
    begin, finish = date_range(start, end, days=min(30, max_days), max_days=max_days)
    meta = instrument(user, uid)
    with details.BrokerReader(user) as reader:
        raw = broker_read(reader, 'candles', {'instrumentId': uid, 'from': begin.isoformat(),
            'to': finish.isoformat(), 'interval': enum, 'limit': limit,
            'candleSourceType': 'CANDLE_SOURCE_EXCHANGE'})
    observed = now_iso()
    if not isinstance(raw.get('candles'), list):
        raise HTTPException(502, 'candles_invalid_response')
    quote_currencies = {str(row.get('priceCurrency')).upper() for row in raw.get('candles', []) if isinstance(row, dict) and row.get('priceCurrency')}
    if len(quote_currencies) > 1:
        raise HTTPException(502, 'candles_currency_changed_in_range')
    unit, label, currency = quote_unit(meta, next(iter(quote_currencies), raw.get('priceCurrency')))
    ref = source('GetCandles', uid, observed, url=DOCS + 'market-data-service-get-candles',
                 unit=unit, currency=currency, ttl=60)
    rows = normalize_candles(raw.get('candles'), observed_at=observed, source_id=ref['id'])
    # A full provider page is not a proof that the whole requested range fits.
    limited = len(rows) >= limit
    event_section = safe_section(lambda: instrument_events(user, uid, meta, begin, finish), empty={'items': []})
    return {'schema_version': SCHEMA_VERSION, 'instrument_uid': uid, 'interval': interval,
            'start': begin.isoformat(), 'end': finish.isoformat(), 'as_of': observed,
            'state': 'partial' if limited else 'available',
            'reason': 'provider_candle_limit_reached' if limited else None,
            'unit': unit, 'unit_label': label, 'currency': currency, 'sources': [ref, *event_section.get('sources', [])],
            'candles': rows, 'events': (event_section.get('data') or {}).get('items', []),
            'events_state': event_section['state'], 'gaps_filled': False,
            'price_basis': 'exchange_quote_not_portfolio_valuation'}


@router.get('/instruments/{uid}/candles', responses=HTTP_ERRORS)
def candles(uid: str, start: date | None = None, end: date | None = None,
            interval: str = Query('day', max_length=30), user: Any = Depends(backend.current_user)) -> dict:
    require_id(uid)
    return details.cached(('workspace-candles', *details.identity(user), uid, start, end, interval),
                          30, lambda: load_candles(user, uid, start, end, interval))


def instrument_events(user: Any, uid: str, meta: dict, begin: datetime, finish: datetime) -> dict:
    items, refs, errors = [], [], []
    methods = [('reports', 'events', 'report')]
    kind = instrument_kind(meta)
    if kind == 'bond':
        methods.append(('coupons', 'events', 'coupon'))
    elif kind == 'share':
        methods.append(('dividends', 'dividends', 'dividend'))
    with details.BrokerReader(user) as reader:
        for method, field, event_kind in methods:
            body = {'instrumentId': uid, 'from': begin.isoformat(), 'to': finish.isoformat()}
            try:
                rows = _instrument_event_rows(reader, method, field, body)
            except HTTPException as error:
                errors.append(error_code(error))
                continue
            ref = source({'reports': 'GetAssetReports', 'coupons': 'GetBondCoupons', 'dividends': 'GetDividends'}[method],
                         uid, now_iso(), url=DOCS + 'instruments-service', ttl=3600)
            refs.append(ref)
            for raw_event in rows:
                event = _instrument_event(raw_event, event_kind, uid, begin, finish, ref, errors)
                if event is not None:
                    items.append(event)
    return section({'items': sorted(items, key=lambda item: item['date']), 'errors': errors},
                   state='partial' if errors else 'available', reason=errors[0] if errors else None,
                   as_of=now_iso(), sources=refs)


def _news_uids(raw: dict) -> list[str]:
    try:
        from .volume_news import instrument_uids
    except ImportError:
        from volume_news import instrument_uids
    return instrument_uids(raw)


def deduplicate_news(rows: list[dict], *, uid: str | None, ref: dict) -> list[dict]:
    try:
        from .volume_news import group_news
    except ImportError:
        from volume_news import group_news
    return group_news(rows, uid=uid, ref=ref)[0]


def load_news(user: Any, uid: str | None = None) -> dict:
    rows, complete = _news_pages(user)
    observed = now_iso()
    ref = source('News', 'market-news', observed, url=DOCS + 'instruments-service-news', ttl=300)
    try:
        from .volume_news import group_news
    except ImportError:
        from volume_news import group_news
    items, errors = group_news(rows, uid=uid, ref=ref)
    complete = complete and not errors
    refs = list({r['id']: r for r in [ref] + [proof for item in items for proof in item['evidence_sources']]}.values())
    return section({'items': items, 'complete': complete, 'provider_history_hours': 24, 'errors': errors},
                   state='available' if complete else 'partial',
                   reason=_news_reason(complete, errors), as_of=observed, sources=refs)


def rating_section(uid: str, meta: dict) -> dict:
    at = datetime.now(timezone.utc)
    try:
        identity = research_store.latest_verified(backend.connect, 'issuer_identity', uid, at)
        issuer = identity.get('issuer_id') if identity else None
        history = research_store.records(backend.connect, 'rating', uid, at=at)
        if issuer:
            history += research_store.records(backend.connect, 'rating', issuer, at=at)
        ratings = [Rating(**{**row, 'source': Source(**row['source'])}) for row in history]
        assessment = credit_assessment(ratings, issuer_id=issuer, instrument_id=uid,
                                       at=at, bond=instrument_kind(meta) == 'bond')
    except (ValueError, TypeError, KeyError, EvidenceError):
        return section({'items': [], 'history': [], 'warnings': ['Проверенные рейтинги недоступны.']},
                       state='unavailable', reason='rating_evidence_unavailable')
    return section({'items': assessment['ratings'], 'history': history, 'warnings': assessment['warnings'],
                    'issuer_id': issuer, 'has_required_rating': assessment['has_required_rating'],
                    'scales_are_not_averaged': True},
                   state='available' if assessment['has_required_rating'] else 'partial',
                   reason=None if assessment['has_required_rating'] else 'verified_rating_required',
                   as_of=at.isoformat(), sources=[reviewed_source(row['source'], provider=row['agency'], method='credit_rating', subject=row['subject_id']) for row in history])


FUNDAMENTAL_LABELS = {'revenueTtm': ('Выручка за 12 месяцев', 'currency'),
                      'netIncomeTtm': ('Чистая прибыль за 12 месяцев', 'currency'),
                      'freeCashFlowTtm': ('Свободный денежный поток за 12 месяцев', 'currency'),
                      'netDebtToEbitda': ('Чистый долг / EBITDA', 'ratio'),
                      'currentRatioMrq': ('Текущая ликвидность', 'ratio')}


def _fundamental_value(raw: Any) -> tuple[str | None, str | None]:
    # The broker's double fields use zero as an unavailable-data marker.
    value = decimal(str(raw)) if type(raw) in (int, float, str) else None
    if value == 0:
        return None, 'broker_zero_means_unavailable'
    if value is None:
        return None, 'not_supplied'
    return text_number(value), None


def _fundamental_items(raw: dict, ref: dict) -> list:
    items = []
    for key, (label, unit) in FUNDAMENTAL_LABELS.items():
        value, missing = _fundamental_value(raw.get(key))
        items.append({'id': key, 'label': label, 'value': value, 'unit': unit,
                      'currency': raw.get('currency') if unit == 'currency' else None,
                      'period': raw.get('fiscalPeriodEndDate'), 'source_ids': [ref['id']], 'missing_reason': missing})
    return items


def _fundamental_observation(raw: dict) -> dict:
    result = {}
    for key, value in raw.items():
        if key == 'assetUid':
            continue
        numeric = type(value) in (int, float) or (isinstance(value, str) and decimal(value) is not None)
        if numeric or key in FUNDAMENTAL_LABELS:
            result[key] = _fundamental_value(value)[0]
        else:
            result[key] = value
    return result


def _fundamental_conflict(rows: list, ref: dict) -> dict:
    bases = {(row.get('fiscalPeriodEndDate'), row.get('currency')) for row in rows}
    observations = []
    for row in rows:
        items = _fundamental_items(row, ref)
        observations.append({'source_id': ref['id'], 'value': _fundamental_observation(row),
                             'period': row.get('fiscalPeriodEndDate'), 'currency': row.get('currency'),
                             'metrics': items})
    return {'label': 'Расхождение фундаментальных показателей', 'basis_matches': len(bases) == 1,
            'reason': 'same_basis_different_values' if len(bases) == 1 else 'different_period_or_currency',
            'observations': observations, 'source_ids': [ref['id']]}


def metric_section(user: Any, uid: str, meta: dict) -> dict:
    asset_uid = meta.get('assetUid')
    if not asset_uid:
        return section({'instrument_uid': uid, 'items': [], 'conflicts': []}, state='unavailable', reason='asset_identity_required')
    with details.BrokerReader(user) as reader:
        raw = broker_read(reader, 'fundamentals', {'assets': [asset_uid]})
    rows = [row for row in raw.get('fundamentals', []) if isinstance(row, dict) and row.get('assetUid') == asset_uid]
    observed = now_iso()
    ref = source('GetAssetFundamentals', asset_uid, observed,
                 url=DOCS + 'instruments-service-get-asset-fundamentals', ttl=3600)
    if not rows:
        return section({'instrument_uid': uid, 'items': [], 'conflicts': []}, state='unavailable', reason='fundamentals_not_supplied', sources=[ref])
    # Compare the basis before calling different observations contradictory.
    unique = {digest(row): row for row in rows}
    if len(unique) > 1:
        return section({'instrument_uid': uid, 'items': [], 'conflicts': [_fundamental_conflict(list(unique.values()), ref)]},
            state='partial', reason='fundamentals_conflict', as_of=observed, sources=[ref])
    items = _fundamental_items(rows[0], ref)
    return section({'instrument_uid': uid, 'items': items, 'conflicts': [], 'basis': 'broker_metrics_not_audited_statement'},
                   state='partial' if any(item['missing_reason'] for item in items) else 'available',
                   reason='some_fundamentals_unavailable' if any(item['missing_reason'] for item in items) else None,
                   as_of=observed, sources=[ref])


def trading_section(user: Any, uid: str, meta: dict) -> dict:
    with details.BrokerReader(user) as reader:
        raw = broker_read(reader, 'trading_status', {'instrumentId': uid})
    observed = now_iso()
    ref = source('GetTradingStatus', uid, observed, ttl=30)
    if raw.get('instrumentUid') not in {None, uid}:
        raise HTTPException(502, 'trading_status_identity_mismatch')
    return section({'status': raw.get('tradingStatus'), 'api_trade_available': raw.get('apiTradeAvailableFlag'),
                    'limit_order_available': raw.get('limitOrderAvailableFlag'), 'market_order_available': raw.get('marketOrderAvailableFlag'),
                    'required_tests': meta.get('requiredTests'), 'execution_guaranteed': False}, as_of=observed, sources=[ref])


@financial_context
def liquidity_section(user: Any, uid: str, meta: dict) -> dict:
    with details.BrokerReader(user) as reader:
        raw = broker_read(reader, 'order_book', {'instrumentId': uid, 'depth': 1})
    if raw.get('instrumentUid') != uid:
        raise HTTPException(502, 'order_book_identity_mismatch')
    observed = now_iso()
    ref = source('GetOrderBook', uid, observed, ttl=30)
    try:
        age = (timestamp(observed) - timestamp(raw.get('orderbookTs'))).total_seconds()
        current = 0 <= age < 60
    except ValueError:
        current = False
    def side(name):
        rows = raw.get(name, [])
        if not isinstance(rows, list):
            raise HTTPException(502, 'order_book_value_invalid')
        if not rows:
            return None
        if not isinstance(rows[0], dict):
            raise HTTPException(502, 'order_book_value_invalid')
        price, quantity = decimal(rows[0].get('price')), decimal(rows[0].get('quantity'))
        if price is None or price <= 0 or quantity is None or quantity <= 0 or quantity != quantity.to_integral_value():
            raise HTTPException(502, 'order_book_value_invalid')
        return {'price': text_number(price), 'quantity_lots': text_number(quantity)}
    bid, ask = side('bids'), side('asks')
    unit, label, currency = quote_unit(meta)
    spread = decimal(ask['price']) - decimal(bid['price']) if bid and ask else None
    if spread is not None and spread < 0:
        raise HTTPException(502, 'order_book_crossed_observation')
    # Unary GetOrderBookResponse has orderbookTs, not the stream's isConsistent.
    # Absence is not a consistency assertion; reject an explicit adverse flag.
    consistency = raw.get('isConsistent')
    flag_acceptable = 'isConsistent' not in raw or consistency is True
    reason = None
    if not current:
        reason = 'order_book_stale_or_undated'
    elif not bid or not ask or not flag_acceptable:
        reason = 'order_book_empty_or_not_consistent'
    return section({'best_bid': bid, 'best_ask': ask, 'spread': text_number(spread), 'unit': unit, 'unit_label': label,
                    'currency': currency, 'depth_consistent': consistency if type(consistency) is bool else None,
                    'basis': 'observed_top_of_book_not_guarantee_of_liquidation_or_execution'},
                   state='available' if reason is None else 'partial',
                   reason=reason, as_of=observed, sources=[ref])


def load_dossier(user: Any, uid: str) -> dict:
    meta = instrument(user, uid)
    observed = now_iso()
    ref = meta.get('_source') or source('GetInstrumentBy', uid, observed, url=DOCS + 'instruments-service-get-instrument-by', ttl=300)
    kind = instrument_kind(meta)
    snapshot = details.dashboard(currency='RUB', user=user)
    holdings = [{'account_id': account['id'], 'account_name': account['name'],
        'quantity': text_number(decimal(position.get('quantity'))), 'value': money(position.get('currentValue')),
        'blocked': bool(position.get('blocked'))}
        for account in snapshot.get('accounts', []) for position in account.get('positions', []) if position.get('id') == uid]
    begin = datetime.now(timezone.utc) - timedelta(days=30)
    finish = begin + timedelta(days=395)
    events = safe_section(lambda: instrument_events(user, uid, meta, begin, finish), empty={'items': []})
    rating = rating_section(uid, meta)
    try:
        issuer_identity = research_store.latest_verified(backend.connect, 'issuer_identity', uid, datetime.now(timezone.utc))
    except EvidenceError:
        issuer_identity = None
    reports = [row for row in (events.get('data') or {}).get('items', []) if row['kind'] == 'report']
    try:
        issuer = (rating.get('data') or {}).get('issuer_id')
        statement = research_store.latest_verified(backend.connect, 'statement', issuer, datetime.now(timezone.utc)) if issuer else None
    except EvidenceError:
        statement = None
    if statement:
        reports.append({'id': digest(statement), 'date': statement['source']['published_at'],
                        'title': 'Опубликованная проверенная отчётность',
                        'status': 'published', 'source_ids': [statement['source']['id']],
                        'source': reviewed_source(statement['source'], provider='Reviewed issuer report', method='statement', subject=issuer), 'period_start': statement.get('period_start'),
                        'period_end': statement.get('period_end')})
    sections = {
        'instrument': section({'uid': uid, 'title': meta.get('name'), 'ticker': meta.get('ticker'),
            'isin': meta.get('isin'), 'instrument_type': kind, 'lot': meta.get('lot'),
            'currency': meta.get('currency'), 'country_of_risk': meta.get('countryOfRisk'),
            'sector': meta.get('sector'), 'broker_url': instrument_link(kind, meta.get('ticker'), meta.get('isin')),
            'issuer_id': issuer_identity.get('issuer_id') if issuer_identity else None,
            'issuer_name': issuer_identity.get('issuer_name') if issuer_identity else None,
            'issuer_source': reviewed_source(issuer_identity['source'], provider='Reviewed issuer register', method='issuer_identity', subject=uid) if issuer_identity else None,
            'required_tests': meta.get('requiredTests', []), 'api_trade_available': meta.get('apiTradeAvailableFlag'),
            'access_is_read_only': True}, as_of=ref['observed_at'], sources=[ref]),
        'holdings': section({'items': holdings}, as_of=snapshot.get('asOf')),
        'ratings': rating,
        'metrics': safe_section(lambda: metric_section(user, uid, meta), empty={'items': [], 'conflicts': []}),
        'reports': section({'items': reports}, state=events['state'], reason=events['reason'], sources=events['sources']),
        'news': safe_section(lambda: details.cached(('workspace-news', *details.identity(user)), 300,
                            lambda: load_news(user)), empty={'items': []}),
        'events': events,
        'trading': safe_section(lambda: trading_section(user, uid, meta), empty={}),
        'liquidity': safe_section(lambda: liquidity_section(user, uid, meta), empty={}),
    }
    sections['news']['data']['items'] = [row for row in sections['news']['data'].get('items', []) if uid in row['instrument_uids']]
    if issuer_identity:
        sections['instrument']['sources'].append(sections['instrument']['data']['issuer_source'])
    if statement:
        sections['reports']['sources'].append(reports[-1]['source'])
    try:
        from .volume_state import broker_key, record
        from .ai_budget import transaction
    except ImportError:
        from volume_state import broker_key, record
        from ai_budget import transaction
    with transaction(backend.connect) as db:
        record(db, int(user['id']), 'instrument_market', uid, {'instrument_uid': uid, 'broker_key': broker_key(user),
               'trading': sections['trading'], 'liquidity': sections['liquidity'], 'ratings': rating})
    return {'schema_version': SCHEMA_VERSION, 'instrument_uid': uid, 'as_of': observed,
            'sections': sections, 'sources': list({item['id']: item for value in sections.values() for item in value.get('sources', [])}.values()), 'autotrading': False}


def _store_catalog_instruments(raw: dict, kind: str, method: str, identifiers: set, stored: dict) -> None:
    instruments = raw.get('instruments')
    if not isinstance(instruments, list):
        return
    observed = now_iso()
    for item in instruments:
        if isinstance(item, dict) and item.get('uid') in identifiers:
            uid = item['uid']
            stored[uid] = {**item, 'instrumentType': kind, '_source': source(method.title(), uid, observed, ttl=86400)}


def portfolio_metadata(user: Any, positions: list[dict], stored: dict, progress, checkpoint: dict) -> None:
    """Use broker catalog batches before per-UID fallback for large portfolios."""
    methods = {'share': 'shares', 'bond': 'bonds', 'etf': 'etfs', 'currency': 'currencies', 'futures': 'futures', 'option': 'options'}
    wanted = {p['id']: p for p in positions if p.get('instrumentType') != 'cash' and p['id'] not in stored}
    total = len(wanted) + len(stored)
    groups: dict[str, set] = {}
    for uid, item in wanted.items():
        if item.get('instrumentType') in methods:
            groups.setdefault(item['instrumentType'], set()).add(uid)
    with details.BrokerReader(user) as reader:
        for kind, identifiers in groups.items():
            if len(identifiers) < 10:
                continue
            progress('collecting_metadata', checkpoint, completed=len(stored), total=total)
            try:
                raw = broker_read(reader, methods[kind], {'instrumentStatus': 'INSTRUMENT_STATUS_ALL'})
            except HTTPException:
                continue
            _store_catalog_instruments(raw, kind, methods[kind], identifiers, stored)
            progress('collecting_metadata', checkpoint, completed=len(stored), total=total)


@router.get('/instruments/{uid}/dossier', responses=HTTP_ERRORS)
def dossier(uid: str, user: Any = Depends(backend.current_user)) -> dict:
    require_id(uid)
    revision = research_store.revision(backend.connect)
    return details.cached(('workspace-dossier', *details.identity(user), uid, revision), 60,
                          lambda: load_dossier(user, uid))


def load_calendar(user: Any) -> dict:
    # TradingSchedules rejects a from date before the current UTC date.
    # Never turn missing previous-day coverage into an assumed open session.
    today = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time(), timezone.utc)
    begin = today
    finish = today + timedelta(days=6, hours=23, minutes=59)
    with details.BrokerReader(user) as reader:
        raw = broker_read(reader, 'calendar', {'from': begin.isoformat(), 'to': finish.isoformat()})
    exchanges = raw.get('exchanges')
    if not isinstance(exchanges, list):
        raise HTTPException(502, 'calendar_invalid_response')
    observed = now_iso()
    ref = source('TradingSchedules', 'broker-market-sections', observed,
                 url=DOCS + 'instruments-service-trading-schedules', ttl=900)
    return {'schema_version': SCHEMA_VERSION, 'as_of': observed, 'timezone': 'UTC',
            'display_timezones': ['Europe/Moscow', 'device_local'], 'exchanges': exchanges,
            'source': ref, 'basis': 'broker_sections_not_guaranteed_instrument_availability'}


@router.get('/markets/calendar', responses=HTTP_ERRORS)
def calendar(user: Any = Depends(backend.current_user)) -> dict:
    return details.cached(('workspace-calendar', *details.identity(user)), 600, lambda: load_calendar(user))


def _instrument_event_rows(reader, method, field, body):
    raw = broker_read(reader, method, body) if method == 'reports' else reader.read(method, body)
    rows = raw.get(field, [])
    if not isinstance(rows, list):
        raise HTTPException(502, 'events_invalid_response')
    return rows


def _event_date(raw_event, kind):
    if kind == 'report':
        return raw_event.get('reportDate')
    if kind == 'coupon':
        return raw_event.get('couponDate')
    return raw_event.get('paymentDate') or raw_event.get('recordDate')


def _event_details(raw_event, kind):
    if kind == 'report':
        # An elapsed calendar date does not prove publication.
        return 'scheduled', None, 'Дата отчёта по календарю брокера'
    status = 'cancelled' if str(raw_event.get('dividendType', '')).lower() == 'cancelled' else 'announced'
    amount = money(raw_event.get('payOneBond' if kind == 'coupon' else 'dividendNet'))
    return status, amount, 'Купон' if kind == 'coupon' else 'Дивиденд'


def _instrument_event(raw_event, kind, uid, begin, finish, ref, errors):
    if not isinstance(raw_event, dict):
        return None
    if kind == 'report' and raw_event.get('instrumentId') not in {None, uid}:
        errors.append('report_instrument_identity_mismatch')
        return None
    try:
        at = timestamp(_event_date(raw_event, kind))
    except ValueError:
        return None
    if not begin <= at <= finish:
        return None
    status, amount, title = _event_details(raw_event, kind)
    result = {'id': digest({'uid': uid, 'kind': kind, 'event': raw_event}), 'kind': kind,
              'title': title, 'date': at.isoformat(), 'occurred_at': at.isoformat(), 'status': status,
              'per_unit': amount, 'instrument_uids': [uid], 'source_ids': [ref['id']], 'relationship': 'broker_link'}
    if kind == 'report':
        result.update(period_year=raw_event.get('periodYear'), period_num=raw_event.get('periodNum'),
                      period_type=raw_event.get('periodType'), record_created_at=raw_event.get('createdAt'),
                      publication_confirmed=False)
    return result


def _news_pages(user):
    rows, cursor, cursors, complete = [], None, set(), False
    with details.BrokerReader(user) as reader:
        for _ in range(10):
            body = {'limit': 1000}
            if cursor is not None:
                body['cursor'] = cursor
            raw = broker_read(reader, 'news', body)
            if not isinstance(raw.get('items', []), list):
                raise HTTPException(502, 'news_invalid_response')
            rows.extend(raw.get('items', []))
            if not raw.get('hasNext'):
                complete = True
                break
            cursor = str(raw.get('nextCursor') or '')
            if not re.fullmatch(r'\d{1,20}', cursor) or cursor in cursors:
                break
            cursors.add(cursor)
    return rows, complete


def _news_reason(complete, errors):
    if complete:
        return None
    return errors[0] if errors else 'news_page_limit_or_cursor_failure'
