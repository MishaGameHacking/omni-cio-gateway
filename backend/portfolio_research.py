"""Authenticated broker research + conservative portfolio explanations.

No trading endpoints, LLMs, synthetic financial values or rating guesses.
Broker fundamentals/news are labelled separately from reviewed agency/reports.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from math import isfinite
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

try:
    from . import app as backend, portfolio_details as details, research_store
    from .autonomous_ai import get_profile
    from .credit_evidence import Rating, Source, Statement, credit_assessment, statement_analysis, stamp, EvidenceError
    from .investment_links import instrument_link
    from .risk_math import aligned_returns, bootstrap_floor_risk, portfolio_variance, RiskDataError
except ImportError:
    import app as backend
    import portfolio_details as details
    import research_store
    from autonomous_ai import get_profile
    from credit_evidence import Rating, Source, Statement, credit_assessment, statement_analysis, stamp, EvidenceError
    from investment_links import instrument_link
    from risk_math import aligned_returns, bootstrap_floor_risk, portfolio_variance, RiskDataError

router = APIRouter(prefix='/analysis', tags=['portfolio-research'])
ZERO = Decimal(0)
EXTRA_METHODS = {'fundamentals': 'GetAssetFundamentals', 'news': 'News'}


def optional_broker_read(reader, method: str, payload: dict) -> tuple[dict, str | None]:
    try:
        value = details.portfolio._post_tinvest(reader.client,
            details.BASE + 'InstrumentsService/' + EXTRA_METHODS[method], reader.token, payload)
        return value, None
    except HTTPException:
        return {}, 'Источник временно недоступен; это не означает отсутствие риска.'


def position_amount(position: dict, currency: str) -> Decimal | None:
    value = position.get('currentValue')
    if not isinstance(value, dict) or value.get('currency') != currency:
        return None
    return details.number(value.get('value'))


def _broker_metric(raw: dict, key: str) -> float | None:
    value = raw.get(key)
    if type(value) not in (int, float):
        return None
    return float(value) if isfinite(value) else None


def broker_company_summary(raw: dict, sector: str) -> dict:
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
        matches = any(isinstance(item, dict) and isinstance(item.get('instrument'), dict) and item['instrument'].get('instrumentUid') == uid for item in instruments)
        if not matches:
            continue
        try:
            age = (at - stamp(raw.get('ts', ''))).total_seconds()
        except EvidenceError:
            continue
        if not 0 <= age <= 7 * 86400:
            continue
        result.append({'id': str(raw.get('id', '')), 'title': str(raw.get('title', ''))[:220],
                       'source': str(raw.get('source', ''))[:100], 'published_at': raw['ts'],
                       'important': raw.get('priority') is True,
                       'explanation': 'Новость связана с этой бумагой по данным брокера. Сам заголовок не является командой купить или продать.'})
    return sorted(result, key=lambda item: stamp(item['published_at']), reverse=True)[:3]


def instrument_research(position: dict, profile: dict, total: Decimal, currency: str,
                        fundamentals: dict, news: list, at: datetime) -> dict:
    uid = str(position.get('id', ''))
    identity = research_store.latest_verified(backend.connect, 'issuer_identity', uid, at)
    issuer = identity['issuer_id'] if identity else None
    raw_ratings = research_store.records(backend.connect, 'rating', uid)
    if issuer:
        raw_ratings += research_store.records(backend.connect, 'rating', issuer)
    ratings = [Rating(**{**item, 'source': Source(**item['source'])}) for item in raw_ratings]
    credit = credit_assessment(ratings, issuer_id=issuer, instrument_id=uid, at=at,
                               bond=position.get('instrumentType') == 'bond')
    raw_statement = research_store.latest_verified(backend.connect, 'statement', issuer, at) if issuer else None
    statement = Statement(**{**raw_statement, 'source': Source(**raw_statement['source'])}) if raw_statement else None
    company = statement_analysis(statement, issuer_id=issuer or '', at=at)
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
            'broker_fundamentals': broker_company_summary(fundamentals.get(position.get('assetUid'), {}), str(position.get('sector') or '')),
            'news': relevant_news(news, uid, at),
            'instrument_url': instrument_link(position.get('instrumentType'), position.get('ticker'), position.get('isin')),
            'search_hint': ' · '.join(str(position.get(key)) for key in ('ticker', 'isin', 'title') if position.get(key)),
            'order_created': False, 'target_percent': None}


def _history_risk(cards, values, total, currency, at):
    series, weights = {}, {}
    for card in cards:
        uid = card['instrument_uid']
        record = research_store.latest_verified(backend.connect, 'total_returns', uid, at)
        if record is None or record.get('currency') != currency:
            return {'state': 'insufficient_verified_history', 'default_probability': None,
                    'explanation': 'Нет полной сопоставимой истории с учётом выплат и изменений бумаг. Процент вероятности потери капитала не придумываем.'}
        series[uid], weights[uid] = record['values'], float(values[uid] / total)
    try:
        names, days, rows = aligned_returns(series)
        if days[-1] > at.date().isoformat() or (at.date() - datetime.fromisoformat(days[-1]).date()).days > 7:
            raise RiskDataError('history_not_current')
        w = [weights[name] for name in names]
        return {'state': 'sample_estimate', 'one_session_variance': portfolio_variance(rows, w),
                'sample_start': days[0], 'sample_end': days[-1],
                'scenarios': bootstrap_floor_risk(rows, w),
                'explanation': 'Это проверка сценариев из прошлых данных, а не обещание будущего результата. Новые кризисы могут оказаться хуже.'}
    except (RiskDataError, ValueError):
        return {'state': 'history_quality_failed', 'default_probability': None,
                'explanation': 'История не прошла проверку полноты и сопоставимости.'}


def collect_research(user: Any) -> dict:
    profile = get_profile(int(user['id']))
    snapshot = details.load_dashboard(user, 'RUB')
    total = details.number(snapshot.get('totalValue', {}).get('value'))
    at = datetime.now(timezone.utc)
    positions = {}
    cash = ZERO
    full_cash = True
    complex_valuation = False
    for account in snapshot.get('accounts', []):
        complex_valuation = complex_valuation or bool(account.get('virtualPositions')) or bool(account.get('limitsLoading'))
        for raw in account.get('positions', []):
            if raw.get('instrumentType') == 'cash':
                cash_value = position_amount(raw, 'RUB')
                full_cash = full_cash and cash_value is not None and cash_value >= 0
                cash += cash_value if cash_value is not None else ZERO
                continue
            uid = raw.get('id')
            if uid not in positions:
                positions[uid] = dict(raw)
                positions[uid]['_aggregate_value'] = position_amount(raw, 'RUB')
            else:
                previous = positions[uid]['_aggregate_value']
                value = position_amount(raw, 'RUB')
                positions[uid]['_aggregate_value'] = previous + value if previous is not None and value is not None else None
                positions[uid]['blocked'] = positions[uid].get('blocked', False) or raw.get('blocked', False)
    if total is None or total <= 0:
        return {'state': 'portfolio_required', 'cards': [], 'message': 'Нужен портфель с положительной стоимостью.'}
    selected = list(positions.values())[:100]
    assets = list({p['assetUid'] for p in selected if p.get('assetUid')})
    with details.BrokerReader(user) as reader:
        fundamental_data, fundamental_error = optional_broker_read(reader, 'fundamentals', {'assets': assets}) if assets else ({}, None)
        news_data, news_error = optional_broker_read(reader, 'news', {'limit': 100})
    fundamentals = {item['assetUid']: item for item in fundamental_data.get('fundamentals', []) if isinstance(item, dict) and item.get('assetUid')}
    cards, values = [], {}
    for position in selected:
        value = position['_aggregate_value']
        if value is not None:
            position['currentValue'] = details.portfolio._money_payload(value, 'RUB')
            values[position['id']] = value
        else:
            position['currentValue'] = None
        cards.append(instrument_research(position, profile, total, 'RUB', fundamentals, news_data.get('items', []), at))
    all_valued = (len(values) == len(cards) and len(positions) <= 100
                  and all(v >= 0 for v in values.values()) and full_cash and not complex_valuation
                  and abs(sum(values.values(), ZERO) + cash - total) <= Decimal('.02'))
    sums = defaultdict(Decimal)
    for card in cards:
        if card['issuer_id'] and card['share_percent'] is not None:
            sums[card['issuer_id']] += Decimal(card['share_percent'])
    for card in cards:
        if profile.get('configured') and card['issuer_id'] and sums[card['issuer_id']] > Decimal(str(profile['max_position_percent'])):
            card['issuer_share_percent'] = str(sums[card['issuer_id']])
            if card['action'] != 'restricted':
                card['action'] = 'review_issuer_concentration'
            card['explanation'] += f" Бумаги одной компании вместе занимают {sums[card['issuer_id']]:.1f}% портфеля."
    risk = _history_risk(cards, values, total, 'RUB', at) if all_valued and cards else {
        'state': 'incomplete_valuation', 'default_probability': None,
        'explanation': 'Не все позиции оценены в одной валюте. Полную оценку риска не показываем.'}
    return {'state': 'research', 'as_of': at.isoformat(), 'currency': 'RUB', 'cards': cards,
            'profile_configured': bool(profile.get('configured')), 'risk': risk,
            'source_errors': [e for e in (fundamental_error, news_error) if e],
            'examined_positions': len(cards), 'total_positions': len(positions),
            'issuer_coverage_count': sum(bool(c['issuer_id']) for c in cards),
            'analysis_is_complete': False, 'autotrading': False, 'paid_model_calls': 0,
            'message': 'Выводы по вашему портфелю. Нет обещания доходности или защиты от любого банкротства.',
            'candidate_selection_state': 'verified_universe_required'}


@router.get('/research')
def research(user: Any = Depends(backend.current_user)) -> dict:
    key = (*details.identity(user), 'research-v1')
    return details.cached(key, 300, lambda: collect_research(user))
