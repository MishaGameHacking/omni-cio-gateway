"""Dated credit/statement evidence; conflicting facts must never imply safety."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
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
AGENCIES = {'ACRA': 'acra-ratings.ru', 'EXPERT_RA': 'raexpert.ru',
            'NKR': 'ratings.ru', 'NRA': 'ra-national.ru'}
MINIMUM_CREDIT_GRADE = 'BBB'
MAXIMUM_CREDIT_LEVEL = LEVELS.index(MINIMUM_CREDIT_GRADE)
BROKER_RATING_URL = 'https://developer.tbank.ru/invest/api/instruments-service-bond-by'
BROKER_RATING_MAX_AGE = timedelta(days=366)
BROKER_RATING_OBSERVATION_TTL = timedelta(hours=24)
AGENCY_ALIASES = {
    'acra': 'ACRA', 'акра': 'ACRA',
    'аналитическое кредитное рейтинговое агентство': 'ACRA',
    'expert_ra': 'EXPERT_RA', 'expert ra': 'EXPERT_RA', 'эксперт ра': 'EXPERT_RA',
    'nkr': 'NKR', 'ncr': 'NKR', 'нкр': 'NKR', 'национальные кредитные рейтинги': 'NKR',
    'nra': 'NRA', 'нра': 'NRA', 'национальное рейтинговое агентство': 'NRA',
}
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
    evidence_basis: str = 'agency_publication'
    is_under_watch: bool = False

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
        primary = self.evidence_basis == 'agency_publication' and host in {root, 'www.' + root}
        broker = (self.evidence_basis == 't_invest_bond_rating'
                  and self.source.url == BROKER_RATING_URL and self.subject_kind == 'issue')
        if not primary and not broker:
            return None
        symbol = _national_rating_symbol(self.agency, self.grade)
        return LEVELS.index(symbol) if symbol in LEVELS else None

    def bucket(self) -> str:
        return ':'.join((self.agency, self.scale, self.grade))


def _rating_identity(rating: Rating) -> tuple:
    return (rating.grade, rating.status, rating.outlook, rating.source.url,
            rating.source.expires_at, rating.is_under_watch)


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
    # A freshly fetched broker copy must not replace a primary-source withdrawal.
    key = (rating.agency, rating.scale, rating.subject_kind, rating.subject_id, rating.evidence_basis)
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
        identity = (rating.agency, rating.scale, rating.subject_kind, rating.subject_id, rating.evidence_basis)
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
            or type(first.is_under_watch) is not bool
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
    current.sort(key=lambda item: (item['agency'], item['scale'], item['subject_kind'], item['subject_id'], item['evidence_basis']))
    return _credit_result(current, warnings, bond)


def _credit_result(current: list[dict], warnings: list[str], bond: bool) -> dict:
    relevant = [r for r in current if r['subject_kind'] == ('issue' if bond else 'issuer')]
    if not relevant:
        warnings.append('Нет проверенного рейтинга этого выпуска.' if bond else 'Нет проверенного рейтинга компании.')
    return {'ratings': current, 'warnings': sorted(set(warnings)),
            'has_required_rating': bool(relevant),
            'watch': any(r['is_under_watch'] or r['outlook'] in {'negative', 'developing', 'watch_negative'} for r in current),
            'minimum_grade': MINIMUM_CREDIT_GRADE,
            'within_rating_floor': bool(relevant) and not warnings and all(
                0 <= r['level_within_agency'] <= MAXIMUM_CREDIT_LEVEL for r in current),
            'default_probability': None,
            'explanation': 'Рейтинг — мнение о способности вернуть долг, не обещание дохода и не точный процент риска.'}


def broker_bond_ratings(meta: dict, *, instrument_id: str, observed_at: str,
                       at: datetime) -> tuple[list[Rating], list[str]]:
    """Normalize the official Bond.ratings field, never broker riskLevel.

    The rating belongs to the returned bond. It does not establish the issuer's
    rating or issuer identity. Observation and agency assignment dates remain
    distinct, and neither LLM output nor an unmarked international scale qualifies.
    """
    _assessment_time(at)
    if 'ratings' not in meta:
        return [], []  # Older API observations retain the primary-source path.
    if meta.get('uid') != instrument_id or not isinstance(meta.get('ratings'), list):
        return [], ['broker_rating_identity_or_shape_invalid']
    try:
        observed = stamp(observed_at)
    except EvidenceError:
        return [], ['broker_rating_observation_invalid']
    if not observed <= at < observed + BROKER_RATING_OBSERVATION_TTL:
        return [], ['broker_rating_observation_stale_or_future']
    ratings, errors = [], []
    if len(meta['ratings']) > 100:
        return [], ['broker_rating_response_too_large']
    for row in meta['ratings']:
        try:
            ratings.append(_broker_bond_rating(row, instrument_id, observed, at))
        except (EvidenceError, TypeError, ValueError, OverflowError):
            errors.append('broker_rating_unrecognized_ambiguous_or_stale')
    return ratings, sorted(set(errors))


def _broker_bond_rating(row: dict, uid: str, observed: datetime, at: datetime) -> Rating:
    if not isinstance(row, dict):
        raise EvidenceError('broker_rating_shape_invalid')
    name, grade = row.get('agencyName'), row.get('ratingLevel')
    agency = AGENCY_ALIASES.get(name.strip().casefold()) if isinstance(name, str) else None
    if not agency or not isinstance(grade, str) or _national_rating_symbol(agency, grade) not in LEVELS:
        raise EvidenceError('broker_rating_scale_unrecognized')
    assigned = stamp(row.get('ratingDate'))
    if assigned > observed:
        raise EvidenceError('broker_rating_future')
    expires = min(observed + BROKER_RATING_OBSERVATION_TTL, assigned + BROKER_RATING_MAX_AGE)
    if not assigned <= observed <= at < expires:
        raise EvidenceError('broker_rating_stale_or_future')
    watch = row.get('isUnderWatch', False)  # Proto3 omitted bool is false.
    if type(watch) is not bool:
        raise EvidenceError('broker_rating_watch_invalid')
    forecasts = {'стабильный': 'stable', 'stable': 'stable', 'позитивный': 'positive',
                 'positive': 'positive', 'негативный': 'negative', 'negative': 'negative',
                 'развивающийся': 'developing', 'developing': 'developing'}
    forecast = row.get('forecast')
    outlook = forecasts.get(forecast.strip().casefold()) if isinstance(forecast, str) else None
    if outlook is None:
        raise EvidenceError('broker_rating_forecast_unrecognized')
    fingerprint = hashlib.sha256(json.dumps({'uid': uid, 'rating': row, 'observed_at': observed.isoformat()},
        ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()).hexdigest()
    proof = Source('t-invest-rating:' + fingerprint, BROKER_RATING_URL,
                   assigned.isoformat(), observed.isoformat(), expires.isoformat(),
                   'provider-observation:' + fingerprint)
    return Rating(agency, 'RU_NATIONAL_LONG_TERM', grade, 'issue', uid, 'active',
                  outlook, proof, evidence_basis='t_invest_bond_rating', is_under_watch=watch)


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


def _basis_label(value: object) -> str:
    if not isinstance(value, str) or len(value) > 80:
        raise EvidenceError('statement_basis_required')
    text = value.strip()
    if not text or any(ord(char) < 32 or ord(char) == 127 for char in text):
        raise EvidenceError('statement_basis_required')
    return text


def _statement_basis(statement: Statement) -> tuple[str, str, str]:
    sector = _basis_label(statement.sector).casefold()
    standard = _basis_label(statement.standard)
    currency = _basis_label(statement.currency).upper()
    # Validate a currency-code shape, not the currency's value or FX rate.
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        raise EvidenceError('statement_currency_required')
    if not isinstance(statement.values, Mapping):
        raise EvidenceError('statement_basis_required')
    for key in statement.values:
        if (not isinstance(key, str) or not 1 <= len(key) <= 64
                or key != key.strip() or any(ord(char) < 32 or ord(char) == 127 for char in key)):
            raise EvidenceError('invalid_statement_metric')
    return sector, standard, currency


def validated_statement_data(statement: Statement) -> tuple[str, str, str, dict[str, Decimal]]:
    """Validate imported or analysed values against the same numeric basis."""
    sector, standard, currency = _statement_basis(statement)
    values = {key: amount(value) for key, value in statement.values.items()}
    return sector, standard, currency, values


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
    sector, standard, currency, values = validated_statement_data(statement)
    if sector in {'financial', 'financials', 'finance', 'banks', 'insurance'}:
        return {'state': 'sector_model_required', 'ratios': {},
                'messages': ['Для банка или страховой компании нужна отдельная проверка капитала и резервов.'],
                'source': asdict(statement.source)}
    ratios = _statement_ratios(values)
    messages = _statement_messages(values, ratios, statement.audited)
    if 'net_debt_to_ebitda' in ratios:
        messages.append('Долг сопоставлен с результатом за указанный отчётный период, без пересчёта к году. Показатель за полгода нельзя напрямую сравнивать с годовым.')
    return {'state': 'calculated', 'ratios': ratios,
            'messages': messages, 'ratios_annualized': False,
            'standard': standard, 'currency': currency,
            'period_start': statement.period_start, 'period_end': statement.period_end,
            'source': asdict(statement.source), 'default_probability': None}


def _national_rating_symbol(agency: str, grade: str) -> str:
    if agency == 'ACRA':
        return grade[:-4] if grade.endswith('(RU)') else ''
    if agency == 'EXPERT_RA':
        return grade[2:] if grade.startswith('ru') else ''
    if agency == 'NKR':
        return grade[:-3] if grade.endswith('.ru') else ''
    return grade[:-4] if grade.endswith('|ru|') else ''

