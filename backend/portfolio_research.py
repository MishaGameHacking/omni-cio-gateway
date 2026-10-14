"""Authenticated broker research + conservative portfolio explanations.

No trading endpoints, LLMs, synthetic financial values or rating guesses.
Broker fundamentals/news are labelled separately from reviewed agency/reports.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import isfinite
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

try:
    from . import app as backend, portfolio_details as details, research_store
    from .autonomous_ai import get_profile
    from .credit_evidence import Rating, Source, Statement, credit_assessment, statement_analysis, stamp, EvidenceError
    from .investment_links import instrument_link
    from .risk_math import aligned_returns, bootstrap_floor_risk, portfolio_variance, RiskDataError
    from .research_snapshot import aggregate, SnapshotError
    from .research_profile_cache import profile_digest
    from .research_clock import window_for, note_time
except ImportError:
    import app as backend
    import portfolio_details as details
    import research_store
    from autonomous_ai import get_profile
    from credit_evidence import Rating, Source, Statement, credit_assessment, statement_analysis, stamp, EvidenceError
    from investment_links import instrument_link
    from risk_math import aligned_returns, bootstrap_floor_risk, portfolio_variance, RiskDataError
    from research_snapshot import aggregate, SnapshotError
    from research_profile_cache import profile_digest
    from research_clock import window_for, note_time

router = APIRouter(prefix='/analysis', tags=['portfolio-research'])
ZERO = Decimal(0)
EXTRA_METHODS = {'fundamentals': 'GetAssetFundamentals', 'news': 'News'}
EVIDENCE_FAILURE = 'Проверенные сведения не прошли контроль полноты или целостности. Рейтинг и отчётность этой бумаги не используются до исправления источника.'
SOURCE_FAILURE = 'Источник временно недоступен или вернул непригодные данные; это не означает отсутствие риска.'


def optional_broker_read(reader, method: str, payload: dict) -> tuple[dict, str | None]:
    try:
        value = details.portfolio._post_tinvest(reader.client,
            details.BASE + 'InstrumentsService/' + EXTRA_METHODS[method], reader.token, payload)
        field = 'fundamentals' if method == 'fundamentals' else 'items'
        if not isinstance(value, dict) or not isinstance(value.get(field, []), list):
            return {}, SOURCE_FAILURE
        return value, None
    except HTTPException:
        return {}, SOURCE_FAILURE


def position_amount(position: dict, currency: str) -> Decimal | None:
    value = position.get('currentValue')
    if not isinstance(value, dict) or value.get('currency') != currency:
        return None
    return details.number(value.get('value'))


def _broker_metric(raw: dict, key: str) -> float | None:
    value = raw.get(key) if isinstance(raw, dict) else None
    if type(value) not in (int, float):
        return None
    try:
        numeric = float(value)
    except (ValueError, OverflowError):
        return None
    return numeric if isfinite(numeric) else None


def broker_company_summary(raw: dict, sector: str) -> dict:
    raw = raw if isinstance(raw, dict) else {}
    metrics = {key: _broker_metric(raw, key) for key in
               ('revenueTtm', 'netIncomeTtm', 'freeCashFlowTtm', 'netDebtToEbitda', 'currentRatioMrq')}
    messages = []
    if metrics['netIncomeTtm'] is not None and metrics['netIncomeTtm'] < 0:
        messages.append('По данным брокера компания получила убыток за последние 12 месяцев.')
    if sector.lower() not in {'financial', 'financials', 'finance', 'banks', 'insurance'}:
        if metrics['freeCashFlowTtm'] is not None and metrics['freeCashFlowTtm'] < 0:
            messages.append('Свободный денежный поток отрицательный. Нужно проверить причины, а не покупать только из-за низкой цены.')
    return {'origin': 'broker_metrics_not_audited_statement', 'metrics': metrics, 'messages': messages,
            'period_end': raw.get('fiscalPeriodEndDate'), 'currency': raw.get('currency'),
            'full_statement_reviewed': False}


def relevant_news(items: list, uid: str, at: datetime) -> list[dict]:
    result = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        instruments = raw.get('instrumentId', [])
        if not isinstance(instruments, list):
            continue
        matches = any(isinstance(item, dict) and isinstance(item.get('instrument'), dict) and item['instrument'].get('instrumentUid') == uid for item in instruments)
        if not matches:
            continue
        try:
            published = stamp(raw.get('ts', ''))
            note_time(published)
            note_time(published + timedelta(days=7))
            age = (at - published).total_seconds()
        except (EvidenceError, OverflowError):
            continue
        if not 0 <= age <= 7 * 86400:
            continue
        result.append({'id': str(raw.get('id', '')), 'title': str(raw.get('title', ''))[:220],
                       'source': str(raw.get('source', ''))[:100], 'published_at': raw['ts'],
                       'important': raw.get('priority') is True,
                       'explanation': 'Новость связана с этой бумагой по данным брокера. Сам заголовок не является командой купить или продать.'})
    return sorted(result, key=lambda item: stamp(item['published_at']), reverse=True)[:3]


def _reviewed_evidence(uid: str, bond: bool, at: datetime):
    try:
        identity = research_store.latest_verified(backend.connect, 'issuer_identity', uid, at)
        issuer = identity['issuer_id'] if identity else None
        raw = research_store.records(backend.connect, 'rating', uid, at=at)
        if issuer:
            raw += research_store.records(backend.connect, 'rating', issuer, at=at)
        ratings = [Rating(**{**item, 'source': Source(**item['source'])}) for item in raw]
        credit = credit_assessment(ratings, issuer_id=issuer, instrument_id=uid, at=at, bond=bond)
        fact = research_store.latest_verified(backend.connect, 'statement', issuer, at) if issuer else None
        statement = Statement(**{**fact, 'source': Source(**fact['source'])}) if fact else None
        company = statement_analysis(statement, issuer_id=issuer or '', at=at)
        return issuer, credit, company, None
    except (ValueError, TypeError, KeyError, AttributeError):
        # A failed read cannot turn into an old favorable rating or break the
        # entire portfolio. Show an explicit unavailable evidence section.
        credit = credit_assessment([], issuer_id=None, instrument_id=uid, at=at, bond=bond)
        company = statement_analysis(None, issuer_id='', at=at)
        return None, credit, company, EVIDENCE_FAILURE


def instrument_research(position: dict, profile: dict, total: Decimal, currency: str,
                        fundamentals: dict, news: list, at: datetime) -> dict:
    uid = str(position.get('id', ''))
    issuer, credit, company, evidence_error = _reviewed_evidence(uid, position.get('instrumentType') == 'bond', at)
    value = position_amount(position, currency)
    share = value / total * 100 if value is not None and value >= 0 and total > 0 else None
    limit = Decimal(str(profile['max_position_percent']))
    action = 'watch'
    explanation = 'Проверяем факты. Недостаток данных не означает, что бумага безопасна.'
    if profile.get('configured') and share is not None and share > limit:
        action = 'review_reduce'
        explanation = (f'На эту бумагу приходится {share:.1f} ₽ из каждых 100 ₽ портфеля. '
                       f'Ваш предел — {limit:.1f} ₽. Можно рассмотреть уменьшение доли; сначала проверьте цену, комиссию и налог.')
    if not profile.get('configured'):
        explanation = 'Сначала задайте свой профиль и допустимые доли. Пока показываем факты без персонального плана сделок.'
    if position.get('blocked'):
        action = 'restricted'
        explanation = 'Бумага ограничена или заблокирована. Возможность продажи нужно уточнить у брокера.'
    return {'instrument_uid': uid, 'name': position.get('title') or 'Инструмент',
            'ticker': position.get('ticker'), 'isin': position.get('isin'), 'figi': position.get('figi'),
            'class_code': position.get('classCode'), 'instrument_type': position.get('instrumentType'),
            'issuer_id': issuer, 'sector': position.get('sector'), 'share_percent': str(share) if share is not None else None,
            'action': action, 'explanation': explanation, 'credit': credit, 'statement': company,
            'evidence_error': evidence_error,
            'broker_fundamentals': broker_company_summary(fundamentals.get(position.get('assetUid'), {}), str(position.get('sector') or '')),
            'news': relevant_news(news, uid, at),
            'instrument_url': instrument_link(position.get('instrumentType'), position.get('ticker'), position.get('isin')),
            'search_hint': ' · '.join(str(position.get(key)) for key in ('ticker', 'isin', 'title') if position.get(key)),
            'order_created': False, 'target_percent': None}


def _history_series(cards, values, total, currency, at):
    series, weights = {}, {}
    for card in cards:
        uid = card['instrument_uid']
        record = research_store.latest_verified(backend.connect, 'total_returns', uid, at)
        if record is None or record.get('currency') != currency:
            return None
        series[uid], weights[uid] = record['values'], float(values[uid] / total)
    return series, weights


def _history_risk(cards, values, total, currency, at):
    try:
        history = _history_series(cards, values, total, currency, at)
        if history is None:
            return {'state': 'insufficient_verified_history', 'default_probability': None,
                    'explanation': 'Нет полной сопоставимой истории с учётом выплат и изменений бумаг. Процент вероятности потери капитала не придумываем.'}
        series, weights = history
        names, days, rows = aligned_returns(series)
        last_session = datetime.fromisoformat(days[-1]).replace(tzinfo=timezone.utc)
        note_time(last_session)
        note_time(last_session + timedelta(days=8))
        if days[-1] > at.date().isoformat() or (at.date() - datetime.fromisoformat(days[-1]).date()).days > 7:
            raise RiskDataError('history_not_current')
        w = [weights[name] for name in names]
        return {'state': 'sample_estimate', 'one_session_variance': portfolio_variance(rows, w),
                'sample_start': days[0], 'sample_end': days[-1],
                'scenarios': bootstrap_floor_risk(rows, w),
                'explanation': 'Это проверка сценариев из прошлых данных, а не обещание будущего результата. Новые кризисы могут оказаться хуже.'}
    except (ValueError, TypeError, KeyError, OverflowError):
        return {'state': 'history_quality_failed', 'default_probability': None,
                'explanation': 'История не прошла проверку полноты, целостности и сопоставимости.'}


def _optional_inputs(user, selected):
    assets = sorted({p['assetUid'] for p in selected if p.get('assetUid')})
    with details.BrokerReader(user) as reader:
        fundamental_data, fundamental_error = optional_broker_read(reader, 'fundamentals', {'assets': assets}) if assets else ({}, None)
        news_data, news_error = optional_broker_read(reader, 'news', {'limit': 100})
    fundamentals, conflicts = {}, set()
    for item in fundamental_data.get('fundamentals', []):
        uid = item.get('assetUid') if isinstance(item, dict) else None
        if not isinstance(uid, str) or uid not in assets:
            fundamental_error = SOURCE_FAILURE
            continue
        if uid in fundamentals and fundamentals[uid] != item:
            conflicts.add(uid)
        fundamentals[uid] = item
    for uid in conflicts:
        del fundamentals[uid]
    if conflicts:
        fundamental_error = SOURCE_FAILURE
    return fundamentals, news_data.get('items', []), [e for e in (fundamental_error, news_error) if e]


def _research_cards(selected, profile, total, fundamentals, news, at):
    cards, values = [], {}
    for position in selected:
        value = position['_aggregate_value']
        if value is not None:
            position['currentValue'] = details.portfolio._money_payload(value, 'RUB')
            values[position['id']] = value
        else:
            position['currentValue'] = None
        cards.append(instrument_research(position, profile, total, 'RUB', fundamentals, news, at))
    return cards, values


def _issuer_concentration(cards, profile, *, complete):
    sums = defaultdict(Decimal)
    for card in cards:
        if card['issuer_id'] and card['share_percent'] is not None:
            sums[card['issuer_id']] += Decimal(card['share_percent'])
    coverage = complete and all(c['issuer_id'] and c['share_percent'] is not None for c in cards)
    if not profile.get('configured'):
        return
    limit = Decimal(str(profile['max_position_percent']))
    for card in cards:
        issuer = card['issuer_id']
        if not issuer or sums[issuer] <= limit:
            continue
        card['issuer_share_percent'] = str(sums[issuer])
        card['issuer_share_is_lower_bound'] = not coverage
        if card['action'] != 'restricted':
            card['action'] = 'review_issuer_concentration'
        qualifier = '' if coverage else 'не менее '
        card['explanation'] += f" Проверенные бумаги одной компании вместе занимают {qualifier}{sums[issuer]:.1f}% портфеля."


def collect_research(user: Any, *, profile: dict | None = None) -> dict:
    if profile is None:
        profile = get_profile(int(user['id']))
    snapshot = details.load_dashboard(user, 'RUB')
    total = details.number(snapshot.get('totalValue', {}).get('value'))
    at = datetime.now(timezone.utc)
    if total is None or total <= 0:
        return {'state': 'portfolio_required', 'cards': [], 'message': 'Нужен портфель с положительной стоимостью.'}
    try:
        inventory = aggregate(snapshot, position_amount, 'RUB')
    except SnapshotError:
        raise HTTPException(502, detail='research_snapshot_inconsistent') from None
    selected = list(inventory.positions.values())[:100]
    fundamentals, news, errors = _optional_inputs(user, selected)
    cards, values = _research_cards(selected, profile, total, fundamentals, news, at)
    complete = inventory.fully_valued(values, total)
    _issuer_concentration(cards, profile, complete=complete)
    risk = _history_risk(cards, values, total, 'RUB', at) if complete and cards else {
        'state': 'incomplete_valuation', 'default_probability': None,
        'explanation': 'Не все позиции оценены в одной валюте. Полную оценку риска не показываем.'}
    if any(card['evidence_error'] for card in cards):
        errors.append(EVIDENCE_FAILURE)
    return {'state': 'research', 'as_of': at.isoformat(), 'currency': 'RUB', 'cards': cards,
            'profile_configured': bool(profile.get('configured')), 'risk': risk,
            'source_errors': errors,
            'examined_positions': len(cards), 'total_positions': len(inventory.positions),
            'issuer_coverage_count': sum(bool(c['issuer_id']) for c in cards),
            'analysis_is_complete': False, 'autotrading': False, 'paid_model_calls': 0,
            'message': 'Выводы по вашему портфелю. Нет обещания доходности или защиты от любого банкротства.',
            'candidate_selection_state': 'verified_universe_required'}


def _current_evidence_revision():
    try:
        return research_store.revision(backend.connect)
    except EvidenceError:
        raise HTTPException(503, detail='research_evidence_unavailable') from None


@router.get('/research', responses={
    400: {'description': 'Broker connection is required'},
    502: {'description': 'Broker snapshot cannot support a consistent analysis'},
    503: {'description': 'Profile or evidence changed/unavailable; retry a consistent research snapshot'},
})
def research(user: Annotated[Any, Depends(backend.current_user)]) -> dict:
    identity = details.identity(user)
    profile = get_profile(int(user['id']))
    digest = profile_digest(profile)
    revision = _current_evidence_revision()
    window = window_for((*identity, revision, digest))
    key = (*identity, 'research-v5', revision, window.serial, digest)
    def load():
        with window.observing():
            return collect_research(user, profile=profile)
    result = details.cached(key, 300, load)
    # A profile edit while broker reads are in flight must not publish a result
    # labelled with the user's previous limit. Retry against the new snapshot.
    if profile_digest(get_profile(int(user['id']))) != digest:
        raise HTTPException(503, detail='research_profile_changed')
    # Even a cache hit is rechecked: an import/withdrawal during the request
    # must not publish a mixed or previously favorable evidence snapshot.
    if _current_evidence_revision() != revision:
        raise HTTPException(503, detail='research_evidence_changed')
    if not window.current():
        raise HTTPException(503, detail='research_time_boundary_crossed',
                            headers={'Cache-Control': 'no-store', 'Retry-After': '1'})
    return result
