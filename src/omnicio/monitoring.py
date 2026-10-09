"""Bounded read-only portfolio work, shared by workers and durable scheduling.

Durations below are operational policy, not freshness promises. A provider outage
must stay visible even when a retry is due. Values do not grant broker writes or
relax the per-user connection, consent and database-lock checks.
"""

from datetime import timedelta

# Worker budgets are per process/run; database locks still serialize each owner.
MAX_WORKERS = 2
QUICK_REFRESH_BUDGET_SECONDS = 35
PROVIDER_READ_ATTEMPTS = 3
REFRESH_ADMISSION_SLOTS = 2
WORKER_POLL_SECONDS = 2
WORKER_SHUTDOWN_SECONDS = 5

# Latest news and durable continuations share this bounded work allowance.
NEWS_MAX_PAGES_PER_RUN = 3
NEWS_BUDGET_SECONDS = 12
NEWS_MAX_CONTINUATIONS = 64
NEWS_MAX_PATH_PROOFS = 128
NEWS_MAX_COMPLETED_CURSORS = 64

# Manual admission cooldown differs from snapshot freshness and full enrichment.
REFRESH_COOLDOWN_SECONDS = 60
REFRESH_MAX_ATTEMPTS = 3
DAILY_MAX_ATTEMPTS = 3
MONITORING_FULL_INTERVAL = timedelta(hours=1)
DAILY_RUNNING_TIMEOUT = timedelta(minutes=30)
# Daily retry n waits base * 2**(min(n, max_attempts)-1) seconds, including the
# final terminal record; raising retry count must be an explicit policy change.
DAILY_RETRY_BASE_SECONDS = 300
