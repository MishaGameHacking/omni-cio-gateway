from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlparse

from omni_cio.watchtower.qstash_v1 import (
    QStashScheduleClientV1,
    QStashScheduleError,
    QStashScheduleSpecV1,
)


SCHEDULE_ID = "omni-cio-watchtower-primary-v1"


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise QStashScheduleError(f"{name} is required")
    return value


def _spec() -> QStashScheduleSpecV1:
    base = (
        os.getenv("WATCHTOWER_PUBLIC_BASE_URL", "").strip()
        or os.getenv("RENDER_EXTERNAL_URL", "").strip()
    ).rstrip("/")
    cron = _required("WATCHTOWER_CRON")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path not in {"", "/"}:
        raise QStashScheduleError(
            "WATCHTOWER_PUBLIC_BASE_URL must be a bare HTTPS origin"
        )
    schedule_id = os.getenv("WATCHTOWER_QSTASH_SCHEDULE_ID", SCHEDULE_ID).strip()
    return QStashScheduleSpecV1(
        schedule_id=schedule_id,
        cron=cron,
        destination_url=f"{base}/internal/watchtower/run",
        callback_url=f"{base}/internal/watchtower/callback",
        failure_callback_url=f"{base}/internal/watchtower/failure-callback",
        retries=3,
    )


def _matches(status, spec: QStashScheduleSpecV1) -> bool:
    return bool(
        status is not None
        and status.schedule_id == spec.schedule_id
        and status.cron == spec.cron
        and status.destination == spec.destination_url
        and status.method.upper() == "POST"
        and not status.is_paused
        and status.retries == spec.retries
        and status.callback == spec.callback_url
        and status.failure_callback == spec.failure_callback_url
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check or reconcile the canonical Omni-CIO Watchtower QStash schedule."
    )
    parser.add_argument(
        "--ensure",
        action="store_true",
        help="Create/overwrite the canonical schedule when current state differs.",
    )
    args = parser.parse_args(argv)
    try:
        spec = _spec()
        client = QStashScheduleClientV1(_required("QSTASH_TOKEN"))
        current = client.get_schedule(spec.schedule_id)
        if _matches(current, spec):
            assert current is not None
            print(
                "Watchtower schedule matches canonical configuration: "
                f"id={current.schedule_id} next_ms={current.next_schedule_time_ms}"
            )
            return 0
        if not args.ensure:
            print(
                "Watchtower schedule drift detected; run with --ensure after review.",
                file=sys.stderr,
            )
            return 1
        committed = client.ensure_schedule(spec)
        print(
            "Watchtower schedule reconciled: "
            f"id={committed.schedule_id} next_ms={committed.next_schedule_time_ms}"
        )
        return 0
    except QStashScheduleError as exc:
        print(f"Watchtower schedule reconciliation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
