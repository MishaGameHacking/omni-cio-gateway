"""News grouping with inspectable publications and reviewed original links.

The broker does not supply original/repost relationships. A news_event import
must bind the reviewed event and publication role to observation_fingerprint
of the exact broker item. Headline similarity never establishes that link.
"""
from contextlib import closing

try:
    from . import app as backend, research_store
    from .credit_evidence import EvidenceError, Source
    from .volume_contract import digest, timestamp, reviewed_source
except ImportError:
    import app as backend
    import research_store
    from credit_evidence import EvidenceError, Source
    from volume_contract import digest, timestamp, reviewed_source


def instrument_uids(raw: dict) -> list[str]:
    values = raw.get('instrumentId', [])
    if not isinstance(values, list):
        return []
    return sorted({row['instrument']['instrumentUid'] for row in values
        if isinstance(row, dict) and isinstance(row.get('instrument'), dict)
        and isinstance(row['instrument'].get('instrumentUid'), str)})


def observation_fingerprint(raw: dict) -> str:
    return digest({key: raw.get(key) for key in ('id', 'source', 'title', 'content', 'summary', 'ts', 'instrumentId')})


def _records(rows: list[dict], observed: str) -> tuple[dict, list[str]]:
    valid, conflicted, errors = {}, set(), []
    for raw in rows:
        if not isinstance(raw, dict):
            errors.append('news_record_invalid')
            continue
        identifier = str(raw.get('id') or '')
        try:
            stamp = timestamp(raw.get('ts'))
            if not identifier or not isinstance(raw.get('title'), str) or not raw['title'].strip() or stamp > timestamp(observed):
                raise ValueError
        except ValueError:
            errors.append('news_identity_or_timestamp_invalid')
            continue
        if identifier in valid and observation_fingerprint(valid[identifier]) != observation_fingerprint(raw):
            conflicted.add(identifier)
        valid[identifier] = raw
    for identifier in conflicted:
        del valid[identifier]
    if conflicted:
        errors.append('news_id_conflicting_observations')
    return valid, sorted(set(errors))


def _reviewed_links(items: dict, at) -> dict:
    # Read only subjects present in the current broker response. Batch below
    # SQLite's conservative variable limit; zero imports means zero full reads.
    candidates = set()
    identifiers = list(items)
    with closing(backend.connect()) as db:
        research_store.initialize(db)
        for offset in range(0, len(identifiers), 500):
            chunk = identifiers[offset:offset + 500]
            marks = ','.join('?' for _ in chunk)
            rows = db.execute(f"SELECT DISTINCT subject FROM research_evidence_v1 WHERE kind='news_event' AND subject IN ({marks})", chunk)
            candidates.update(row[0] for row in rows)
    result = {}
    for identifier in candidates:
        record = research_store.latest_verified(backend.connect, 'news_event', identifier, at)
        if record and record['news_sha256'] == observation_fingerprint(items[identifier]):
            primary = record.get('primary_source')
            if primary is None or Source(**primary).valid(at):
                result[identifier] = record
    return result


def _grouping(raw: dict, reviewed: dict | None, uids: list[str]) -> tuple[str, str]:
    if reviewed:
        return 'event:' + reviewed['event_id'], 'reviewed_event_identity'
    # Equal nonempty article content is an observable duplicate of a
    # publication. It still does not identify its author or original source.
    content = raw.get('content')
    if isinstance(content, str) and content.strip():
        return digest([raw['title'], content, raw.get('summary'), timestamp(raw['ts']).date().isoformat(), uids]), 'identical_publication_content'
    return 'news:' + str(raw['id']), 'broker_news_id'


def _origin(raw: dict, review: dict | None, ref: dict) -> tuple[dict, list[dict], dict | None]:
    origin = {'provider': str(raw.get('source') or 'T-Invest')[:160], 'source_id': ref['id'],
              'broker_news_id': str(raw['id']), 'published_at': timestamp(raw['ts']).isoformat(),
              'publication_role': 'unknown', 'publication_role_basis': 'not_supplied_by_broker',
              'url': None, 'review_source_id': None}
    if review is None:
        return origin, [], None
    proof = reviewed_source(review['source'], provider=origin['provider'], method='reviewed_news_event', subject=str(raw['id']))
    origin.update(publication_role=review['publication_role'], publication_role_basis='operator_reviewed_exact_observation',
                  url=proof['url'], review_source_id=proof['id'])
    primary = reviewed_source(review['primary_source'], provider='Reviewed original publication', method='news_primary_source',
                              subject=review['event_id']) if review.get('primary_source') else None
    return origin, [proof] + ([primary] if primary else []), primary


def group_news(rows: list[dict], *, uid: str | None, ref: dict) -> tuple[list[dict], list[str]]:
    items, errors = _records(rows, ref['observed_at'])
    try:
        links = _reviewed_links(items, timestamp(ref['observed_at']))
    except (EvidenceError, KeyError, ValueError, TypeError):
        links = {}
        errors.append('news_review_evidence_unavailable')
    groups = {}
    for identifier, raw in items.items():
        uids = instrument_uids(raw)
        if uid and uid not in uids:
            continue
        review = links.get(identifier)
        key, basis = _grouping(raw, review, uids)
        group = groups.setdefault(key, {'id': key, 'title': raw['title'].strip()[:500],
            'published_at': timestamp(raw['ts']).isoformat(), 'sources': [], 'source_ids': [ref['id']],
            'instrument_uids': [], 'relationship': 'broker_link', 'deduplication': basis,
            'summary': str(raw.get('summary') or '')[:1500], 'event_identity_verified': review is not None,
            'primary_sources': [], 'evidence_sources': []})
        origin, proofs, primary = _origin(raw, review, ref)
        group['sources'].append(origin)
        group['instrument_uids'] = sorted(set(group['instrument_uids']) | set(uids))
        group['published_at'] = max(group['published_at'], origin['published_at'])
        group['evidence_sources'] = list({p['id']: p for p in group['evidence_sources'] + proofs}.values())
        group['source_ids'] = sorted(set(group['source_ids']) | {p['id'] for p in proofs})
        if primary and primary not in group['primary_sources']:
            group['primary_sources'].append(primary)
    return sorted(groups.values(), key=lambda item: item['published_at'], reverse=True), errors
