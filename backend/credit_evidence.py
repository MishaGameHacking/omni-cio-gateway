"""Dated credit/statement evidence; conflicting facts must never imply safety."""
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
        if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
            return False
        if any(not isinstance(value, str) or not value.strip() for value in (self.id, self.review_id, self.url)):
            return False
        try:
            parsed = urlsplit(self.url)
            if parsed.scheme != 'https' or not parsed.hostname:
                return False
            if parsed.username or parsed.password or parsed.fragment or parsed.port not in (None, 443):
                return False
            published, checked, expires = (stamp(x) for x in (self.published_at, self.checked_at, self.expires_at))
            return published <= checked <= at < expires
        except (ValueError, TypeError, AttributeError):
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
        if (self.scale != 'RU_NATIONAL_LONG_TERM' or not isinstance(self.agency, str)
                or self.agency not in AGENCIES or not isinstance(self.grade, str)
                or not isinstance(self.source, Source) or not isinstance(self.source.url, str)):
            return None
        try:
            host = urlsplit(self.source.url).hostname
        except ValueError:
            return None
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


def _rating_identity(rating: Rating) -> tuple:
    # Distinct import IDs are allowed for duplicate observations of the SAME fact.
    return (rating.grade, rating.status, rating.outlook, rating.source.url,
            rating.source.expires_at)


def credit_assessment(ratings: Iterable[Rating], *, issuer_id: str | None,
                      instrument_id: str, at: datetime, bond: bool) -> dict:
    """Latest action wins; conflicting simultaneous actions are quarantined.

    An expired/withdrawn latest rating cannot resurrect a favorable older rating.
    A tie must not depend on database ordering. Agencies/scales remain separate.
    """
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise EvidenceError('assessment_timezone_required')
    latest: dict[tuple, tuple[tuple, list[Rating]]] = {}
    warnings = []
    for rating in ratings:
        if not isinstance(rating, Rating) or not isinstance(rating.source, Source):
            warnings.append('Некорректная запись рейтинга исключена из оценки.')
            continue
        subject_match = ((rating.subject_kind == 'issue' and rating.subject_id == instrument_id)
                         or (rating.subject_kind == 'issuer' and issuer_id and rating.subject_id == issuer_id))
        if not subject_match:
            continue
        if any(not isinstance(value, str) for value in (rating.agency, rating.scale, rating.subject_kind, rating.subject_id)):
            warnings.append('Некорректная запись рейтинга исключена из оценки.')
            continue
        try:
            published, checked = stamp(rating.source.published_at), stamp(rating.source.checked_at)
        except EvidenceError:
            # No trustworthy ordering is possible. Do not fall back to older data.
            warnings.append('Нельзя определить дату действия рейтинга; проверка кредитного качества приостановлена.')
            return _credit_result([], warnings, bond)
        if published > at or checked > at:
            continue
        key = (rating.agency, rating.scale, rating.subject_kind, rating.subject_id)
        moment = (published, checked)
        previous = latest.get(key)
        if previous is None or moment > previous[0]:
            latest[key] = (moment, [rating])
        elif moment == previous[0]:
            previous[1].append(rating)
    current = []
    for _, simultaneous in latest.values():
        first = simultaneous[0]
        if any(_rating_identity(item) != _rating_identity(first) for item in simultaneous[1:]):
            warnings.append('Получены противоречивые рейтинги с одинаковой датой. Они не используются до проверки источника.')
            continue
        # All duplicate observations must be valid; never prefer a valid duplicate
        # while hiding the matching invalid record.
        if first.status != 'active' or not all(item.source.valid(at) for item in simultaneous):
            warnings.append('Рейтинг отсутствует, отозван, просрочен или относится к другой шкале.')
            continue
        level = first.level()
        if level is None:
            warnings.append('Рейтинг отсутствует, отозван, просрочен или относится к другой шкале.')
            continue
        # Stable result even when identical facts arrived in a different order.
        chosen = min(simultaneous, key=lambda item: (item.source.id, item.source.review_id))
        current.append({**asdict(chosen), 'level_within_agency': level, 'bucket': chosen.bucket()})
    current.sort(key=lambda item: (item['agency'], item['scale'], item['subject_kind'], item['subject_id']))
    return _credit_result(current, warnings, bond)


def _credit_result(current: list[dict], warnings: list[str], bond: bool) -> dict:
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
    if type(statement.audited) is not bool:
        raise EvidenceError('audited_boolean_required')
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
