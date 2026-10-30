"""Synthetic broker presence for isolated paid-client tests; no real token."""
from contextlib import closing

from backend.broker_connections import initialize


def bind_synthetic_broker(connect):
    with closing(connect()) as db:
        db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, tinvest_token_encrypted BLOB)')
        db.execute('INSERT INTO users VALUES (1, ?)', (b'synthetic-encrypted-placeholder',))
        db.commit()
    initialize(connect)
