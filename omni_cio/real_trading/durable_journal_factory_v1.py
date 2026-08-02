from __future__ import annotations

import os
from pathlib import Path

from .durable_journal_codec_v1 import JournalStorageError
from .journal_v1 import RealExecutionJournalV1
from .sqlite_journal_v1 import SQLiteRealExecutionJournalV1
from .upstash_journal_v1 import UpstashRealExecutionJournalV1


REAL_JOURNAL_BACKEND_ENV = "REAL_TRADING_JOURNAL_BACKEND"
UPSTASH_REST_URL_ENV = "UPSTASH_REDIS_REST_URL"
UPSTASH_REST_TOKEN_ENV = "UPSTASH_REDIS_REST_TOKEN"
DEFAULT_REAL_JOURNAL_BACKEND = "upstash"


def build_real_execution_journal(
    *,
    gateway_secret: str,
    sqlite_path: Path,
) -> tuple[str, RealExecutionJournalV1]:
    """Build the fail-closed durable backend selected by server environment.

    `upstash` is the production default because it works with Render Free over
    outbound HTTPS. `sqlite` remains an explicit compatibility/test option for
    installations that already have a persistent disk.
    """

    backend = os.environ.get(
        REAL_JOURNAL_BACKEND_ENV, DEFAULT_REAL_JOURNAL_BACKEND
    ).strip().lower()
    if backend == "upstash":
        rest_url = os.environ.get(UPSTASH_REST_URL_ENV, "").strip()
        rest_token = os.environ.get(UPSTASH_REST_TOKEN_ENV, "").strip()
        if not rest_url or not rest_token:
            raise JournalStorageError(
                "UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are required"
            )
        journal = UpstashRealExecutionJournalV1(
            rest_url,
            rest_token,
            gateway_secret=gateway_secret,
        )
    elif backend == "sqlite":
        journal = SQLiteRealExecutionJournalV1(
            sqlite_path,
            gateway_secret=gateway_secret,
        )
    else:
        raise JournalStorageError(
            "REAL_TRADING_JOURNAL_BACKEND must be 'upstash' or 'sqlite'"
        )
    journal.integrity_check()
    return backend, journal
