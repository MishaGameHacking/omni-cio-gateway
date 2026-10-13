"""Dated credit/statement evidence; conflicting facts must never imply safety."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Context, Decimal, DecimalException, InvalidOperation, ROUND_HALF_EVEN, localcontext
from typing import Iterable, Mapping
from urllib.parse import urlsplit


class EvidenceError(ValueError):
    pass


def stamp(value: str) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise EvidenceError('invalid_evidence_time')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (TypeError, ValueError):
        raise EvidenceError('invalid_evidence_time') from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise EvidenceError('evidence_timezone_required')
    return result.astimezone(timezone.utc)


def _assessment_time(at: datetime) -> None:
    if not isinstance(at, datetime) or at.tzinfo is None or at.utcoffset() is None:
        raise EvidenceError('assessment_timezone_required')


def amount(value) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise EvidenceError('missing_numeric_evidence')
    text = str(value)
    if len(text) > 256:
        raise EvidenceError('invalid_numeric_evidence')
    try:
        result = Decimal(text)
    except (InvalidOperation, ValueError):
        raise EvidenceError('invalid_numeric_evidence') from None
    # copy_abs does not round or overflow under a caller's Decimal context.
    if not result.is_finite() or result.copy_abs() > Decimal('1e24'):
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
            _assessment_time(at)
            if not _source_identity_valid(self):
                return False
            published, checked, expires = (stamp(x) for x in
                                          (self.published_at, self.checked_at, self.expires_at))
            return published <= checked <= at < expires
        except (ValueError, TypeError, AttributeError):
            return False


def _source_identity_valid(source: Source) -> bool:
    if any(not isinstance(value, str) or not value.strip()
           for value in (source.id, source.review_id, source.url)):
        return False
    if len(source.url) > 2048 or source.url != source.url.strip():
        return False
    if any(ord(character) < 33 or ord(character) == 127 for character in source.url):
        return False
    parsed = urlsplit(source.url)
    return (parsed.scheme == 'https' and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None
            and not parsed.fragment and parsed.port in (None, 443))


LEVELS = ('AAA', 'AA+', 'AA', 'AA-', 'A+', 'A', 'A-', 'BBB+', 'BBB', 'BBB-',
          'BB+', 'BB', 'BB-', 'B+', 'B', 'B-', 'CCC', 'CC', 'C', 'SD', 'RD', 'D')
AGENCIES = {'ACRA': 'acra-ratings.ru', 'EXPERT_RA': 'raexpert.ru'}
RATING_UNAVAILABLE = 'Рейтинг отсутствует, отозван, просрочен или относится к другой шкале.'
INVALID_RATING = 'Некорректная запись рейтинга исключена из оценки.'


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
    return (rating.grade, rating.status, rating.outlook, rating.source.url,
            rating.source.expires_at)


def _subject_matches(rating: Rating, issuer_id: str | None, instrument_id: str) -> bool:
    if rating.subject_kind == 'issue':
        return rating.subject_id == instrument_id
    return bool(rating.subject_kind == 'issuer' and issuer_id and rating.subject_id == issuer_id)


def _rating_moment(rating: Rating, at: datetime) -> tuple | None:
    published, checked = stamp(rating.source.published_at), stamp(rating.source.checked_at)
    if published > at or checked > at:
        return None
    return published, checked


def _remember_latest(latest: dict, rating: Rating, moment: tuple) -> None:
    key = (rating.agency, rating.scale, rating.subject_kind, rating.subject_id)
    previous = latest.get(key)
    if previous is None or moment > previous[0]:
        latest[key] = (moment, [rating])
    elif moment == previous[0]:
        previous[1].append(rating)


def _latest_ratings(ratings: Iterable[Rating], issuer_id: str | None,
                    instrument_id: str, at: datetime, warnings: list[str]) -> dict:
    latest = {}
    for rating in ratings:
        if not isinstance(rating, Rating) or not isinstance(rating.source, Source):
            warnings.append(INVALID_RATING)
            continue
        if not _subject_matches(rating, issuer_id, instrument_id):
            continue
        identity = (rating.agency, rating.scale, rating.subject_kind, rating.subject_id)
        if any(not isinstance(value, str) for value in identity):
            warnings.append(INVALID_RATING)
            continue
        moment = _rating_moment(rating, at)
        if moment is not None:
            _remember_latest(latest, rating, moment)
    return latest


def _current_rating(simultaneous: list[Rating], at: datetime, warnings: list[str]) -> dict | None:
    first = simultaneous[0]
    if any(_rating_identity(item) != _rating_identity(first) for item in simultaneous[1:]):
        warnings.append('Получены противоречивые рейтинги с одинаковой датой. Они не используются до проверки источника.')
        return None
    if (first.status != 'active' or not isinstance(first.outlook, str)
            or not all(item.source.valid(at) for item in simultaneous)):
        warnings.append(RATING_UNAVAILABLE)
        return None
    level = first.level()
    if level is None:
        warnings.append(RATING_UNAVAILABLE)
        return None
    chosen = min(simultaneous, key=lambda item: (item.source.id, item.source.review_id))
    return {**asdict(chosen), 'level_within_agency': level, 'bucket': chosen.bucket()}


def credit_assessment(ratings: Iterable[Rating], *, issuer_id: str | None,
                      instrument_id: str, at: datetime, bond: bool) -> dict:
    """Keep the latest action, quarantine ties, never resurrect older good news."""
    _assessment_time(at)
    warnings: list[str] = []
    try:
        latest = _latest_ratings(ratings, issuer_id, instrument_id, at, warnings)
    except EvidenceError:
        warnings.append('Нельзя определить дату действия рейтинга; проверка кредитного качества приостановлена.')
        return _credit_result([], warnings, bond)
    current = []
    for _, simultaneous in latest.values():
        row = _current_rating(simultaneous, at, warnings)
        if row is not None:
            current.append(row)
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


def _ratio(numerator: Decimal, denominator: Decimal) -> str:
    try:
        # A server worker must not inherit the arithmetic settings of a caller.
        with localcontext(Context(prec=34, rounding=ROUND_HALF_EVEN, Emax=999, Emin=-999)):
            result = numerator / denominator
    except DecimalException:
        raise EvidenceError('statement_ratio_out_of_range') from None
    if not result.is_finite() or (numerator != 0 and result == 0):
        raise EvidenceError('statement_ratio_out_of_range')
    return str(result)


def _statement_ratios(values: Mapping[str, Decimal]) -> dict[str, str]:
    definitions = {'net_debt_to_ebitda': ('net_debt', 'ebitda'),
                   'interest_coverage': ('ebit', 'interest_expense'),
                   'cash_conversion': ('operating_cash_flow', 'net_income')}
    ratios = {}
    for key, (numerator, denominator) in definitions.items():
        if numerator in values and denominator in values and values[denominator] > 0:
            ratios[key] = _ratio(values[numerator], values[denominator])
    return ratios


def _statement_messages(values: Mapping[str, Decimal], ratios: Mapping[str, str], audited: bool) -> list[str]:
    messages = []
    if values.get('ebitda', Decimal(1)) <= 0:
        messages.append('Основная деятельность не даёт положительного результата до процентов и амортизации; обычное сравнение долга с прибылью здесь ненадёжно.')
    if 'interest_coverage' in ratios and Decimal(ratios['interest_coverage']) < 1:
        messages.append('Прибыли от работы компании за этот период не хватило бы на проценты по долгу.')
    if values.get('free_cash_flow', Decimal(0)) < 0:
        messages.append('После расходов и вложений компания потратила больше денег, чем получила. Нужно проверить, временно ли это.')
    if not audited:
        messages.append('Аудиторское подтверждение этих данных не отмечено.')
    if not ratios:
        messages.append('Данных недостаточно для расчёта долговой нагрузки и покрытия процентов.')
    return messages


def statement_analysis(statement: Statement | None, *, issuer_id: str, at: datetime) -> dict:
    _assessment_time(at)
    if (not isinstance(statement, Statement) or statement.issuer_id != issuer_id
            or not isinstance(statement.source, Source) or not statement.source.valid(at)):
        return {'state': 'missing', 'ratios': {}, 'messages': ['Нет проверенной актуальной отчётности компании.']}
    if type(statement.audited) is not bool:
        raise EvidenceError('audited_boolean_required')
    start, end = stamp(statement.period_start), stamp(statement.period_end)
    if start >= end or end > stamp(statement.source.published_at) or (at - end).days > 550:
        return {'state': 'stale', 'ratios': {}, 'messages': ['Отчётный период не подходит для текущей оценки.']}
    if not isinstance(statement.values, Mapping) or not isinstance(statement.sector, str):
        raise EvidenceError('statement_basis_required')
    values = {key: amount(value) for key, value in statement.values.items()}
    if statement.sector.lower() in {'financial', 'financials', 'finance', 'banks', 'insurance'}:
        return {'state': 'sector_model_required', 'ratios': {},
                'messages': ['Для банка или страховой компании нужна отдельная проверка капитала и резервов.'],
                'source': asdict(statement.source)}
    if not statement.standard or not statement.currency:
        raise EvidenceError('statement_basis_required')
    ratios = _statement_ratios(values)
    return {'state': 'calculated', 'ratios': ratios,
            'messages': _statement_messages(values, ratios, statement.audited),
            'standard': statement.standard, 'currency': statement.currency,
            'period_start': statement.period_start, 'period_end': statement.period_end,
            'source': asdict(statement.source), 'default_probability': None}
