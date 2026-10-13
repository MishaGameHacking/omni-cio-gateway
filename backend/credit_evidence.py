"""Dated credit/statement evidence. Rating opinions are never invented probabilities.

Only an operator-reviewed provider import may write these records. Client APIs
and LLM outputs must not be accepted as authoritative rating/statement evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping
from urllib.parse import urlsplit


class EvidenceError(ValueError):
    pass


def stamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (AttributeError, TypeError, ValueError):
        raise EvidenceError('invalid_evidence_time') from None
    if result.tzinfo is None:
        raise EvidenceError('evidence_timezone_required')
    return result.astimezone(timezone.utc)


def amount(value) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise EvidenceError('missing_numeric_evidence')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise EvidenceError('invalid_numeric_evidence') from None
    if not result.is_finite() or abs(result) > Decimal('1e24'):
        raise EvidenceError('invalid_numeric_evidence')
    return result


@dataclass(frozen=True)
class Source:
    id: str
    url: str
    published_at: str
    checked_at: str
    expires_at: str
    review_id: str

    def valid(self, at: datetime) -> bool:
        try:
            parsed = urlsplit(self.url)
            if not self.id or not self.review_id or parsed.scheme != 'https' or not parsed.hostname:
                return False
            if parsed.username or parsed.password or parsed.fragment or parsed.port not in (None, 443):
                return False
            published, checked, expires = (stamp(x) for x in (self.published_at, self.checked_at, self.expires_at))
            return at.tzinfo is not None and published <= checked <= at < expires
        except (ValueError, TypeError):
            return False


LEVELS = ('AAA', 'AA+', 'AA', 'AA-', 'A+', 'A', 'A-', 'BBB+', 'BBB', 'BBB-',
          'BB+', 'BB', 'BB-', 'B+', 'B', 'B-', 'CCC', 'CC', 'C', 'SD', 'RD', 'D')
AGENCIES = {'ACRA': 'acra-ratings.ru', 'EXPERT_RA': 'raexpert.ru'}


@dataclass(frozen=True)
class Rating:
    agency: str
    scale: str
    grade: str
    subject_kind: str
    subject_id: str
    status: str
    outlook: str
    source: Source

    def level(self) -> int | None:
        # No international/national-scale conversion or implicit symbol repair.
        if self.scale != 'RU_NATIONAL_LONG_TERM' or self.agency not in AGENCIES:
            return None
        host = urlsplit(self.source.url).hostname
        root = AGENCIES[self.agency]
        if host != root and host != 'www.' + root:
            return None
        if self.agency == 'ACRA':
            symbol = self.grade[:-4] if self.grade.endswith('(RU)') else ''
        else:
            symbol = self.grade[2:] if self.grade.startswith('ru') else ''
        return LEVELS.index(symbol) if symbol in LEVELS else None

    def bucket(self) -> str:
        return ':'.join((self.agency, self.scale, self.grade))


def credit_assessment(ratings: Iterable[Rating], *, issuer_id: str | None,
                      instrument_id: str, at: datetime, bond: bool) -> dict:
    """Latest action per agency/scale/subject wins, including a withdrawal.

    Issuer rating may describe the company but does not become its bond rating.
    ACRA vs Expert RA results remain separate; no numeric average is computed.
    """
    latest: dict[tuple, Rating] = {}
    for rating in ratings:
        subject_match = ((rating.subject_kind == 'issue' and rating.subject_id == instrument_id)
                         or (rating.subject_kind == 'issuer' and issuer_id and rating.subject_id == issuer_id))
        if not subject_match or stamp(rating.source.published_at) > at or stamp(rating.source.checked_at) > at:
            continue
        key = (rating.agency, rating.scale, rating.subject_kind, rating.subject_id)
        previous = latest.get(key)
        if previous is None or (stamp(rating.source.published_at), stamp(rating.source.checked_at)) > (
                stamp(previous.source.published_at), stamp(previous.source.checked_at)):
            latest[key] = rating
    current, warnings = [], []
    for rating in latest.values():
        level = rating.level()
        if rating.status != 'active' or not rating.source.valid(at) or level is None:
            warnings.append('Рейтинг отсутствует, отозван, просрочен или относится к другой шкале.')
            continue
        current.append({**asdict(rating), 'level_within_agency': level, 'bucket': rating.bucket()})
    relevant = [r for r in current if r['subject_kind'] == ('issue' if bond else 'issuer')]
    if not relevant:
        warnings.append('Нет проверенного рейтинга этого выпуска.' if bond else 'Нет проверенного рейтинга компании.')
    return {'ratings': current, 'warnings': sorted(set(warnings)),
            'has_required_rating': bool(relevant),
            'watch': any(r['outlook'] in {'negative', 'developing', 'watch_negative'} for r in current),
            'default_probability': None,
            'explanation': 'Рейтинг — мнение о способности вернуть долг, не обещание дохода и не точный процент риска.'}


@dataclass(frozen=True)
class Statement:
    issuer_id: str
    sector: str
    standard: str
    currency: str
    period_start: str
    period_end: str
    values: Mapping[str, str]
    source: Source
    audited: bool = False


def statement_analysis(statement: Statement | None, *, issuer_id: str, at: datetime) -> dict:
    if statement is None or statement.issuer_id != issuer_id or not statement.source.valid(at):
        return {'state': 'missing', 'ratios': {}, 'messages': ['Нет проверенной актуальной отчётности компании.']}
    start, end = stamp(statement.period_start), stamp(statement.period_end)
    if start >= end or end > stamp(statement.source.published_at) or (at - end).days > 550:
        return {'state': 'stale', 'ratios': {}, 'messages': ['Отчётный период не подходит для текущей оценки.']}
    values = {key: amount(value) for key, value in statement.values.items()}
    ratios, messages = {}, []
    if statement.sector.lower() in {'financial', 'financials', 'finance', 'banks', 'insurance'}:
        return {'state': 'sector_model_required', 'ratios': {},
                'messages': ['Для банка или страховой компании нужна отдельная проверка капитала и резервов.'],
                'source': asdict(statement.source)}
    if not statement.standard or not statement.currency:
        raise EvidenceError('statement_basis_required')
    definitions = {'net_debt_to_ebitda': ('net_debt', 'ebitda'),
                   'interest_coverage': ('ebit', 'interest_expense'),
                   'cash_conversion': ('operating_cash_flow', 'net_income')}
    for key, (numerator, denominator) in definitions.items():
        if numerator in values and denominator in values and values[denominator] > 0:
            ratios[key] = str(values[numerator] / values[denominator])
    if values.get('ebitda', Decimal(1)) <= 0:
        messages.append('Основная деятельность не даёт положительного результата до процентов и амортизации; обычное сравнение долга с прибылью здесь ненадёжно.')
    if 'interest_coverage' in ratios and Decimal(ratios['interest_coverage']) < 1:
        messages.append('Прибыли от работы компании за этот период не хватило бы на проценты по долгу.')
    if values.get('free_cash_flow', Decimal(0)) < 0:
        messages.append('После расходов и вложений компания потратила больше денег, чем получила. Нужно проверить, временно ли это.')
    if not statement.audited:
        messages.append('Аудиторское подтверждение этих данных не отмечено.')
    if not ratios:
        messages.append('Данных недостаточно для расчёта долговой нагрузки и покрытия процентов.')
    return {'state': 'calculated', 'ratios': ratios, 'messages': messages,
            'standard': statement.standard, 'currency': statement.currency,
            'period_start': statement.period_start, 'period_end': statement.period_end,
            'source': asdict(statement.source), 'default_probability': None}
