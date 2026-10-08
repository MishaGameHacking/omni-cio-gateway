"""Reviewed 1.2.0 -> 1.3.0 migration in the existing database, without exporting rows.

This module is also sent verbatim to the existing application's Python runtime.
The migration bodies are hash-pinned and share one transaction. A local durable
operation receipt reconciles a lost response after COMMIT without repeating SQL.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import pathlib
import re
import stat
import tomllib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

MODE = "single_existing_database"
RECEIPT_PATH = pathlib.Path("/var/lib/omnicio-upgrade/1.3.0.json")
RELEASE_ROOT = pathlib.Path("/opt/omnicio/releases")
CURRENT_RELEASE = pathlib.Path("/opt/omnicio/current")
PLAN_KEYS = frozenset({
    "mode", "source_release", "source_version", "target_version",
    "source_schema_sha256", "migration_sha256",
})
NEW_SCHEMA_ABSENT = """
SELECT to_regclass('public.assistant_memory') IS NULL
    AND to_regclass('public.notification_push_authorizations') IS NULL
    AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND (
            table_name = 'assistant_requests'
            AND column_name IN ('reply_prefix', 'stream_sequence', 'source_refs', 'updated_at')
            OR table_name = 'notification_channels' AND column_name IN ('session_id', 'binding_id')
            OR table_name = 'notification_outbox' AND column_name = 'binding_id'
        )
    )
"""


class UpgradeBlocked(RuntimeError):
    """A bounded diagnostic code; never include credentials, SQL or row values."""


def _digest(value: str) -> str:
    return hashlib.sha256(value.replace("\r\n", "\n").encode()).hexdigest()


def validate_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != PLAN_KEYS:
        raise UpgradeBlocked("invalid_upgrade_plan")
    if (value["mode"] != MODE or value["source_version"] != "1.2.0"
            or value["target_version"] != "1.3.0"):
        raise UpgradeBlocked("unreviewed_version_transition")
    if (not isinstance(value["source_release"], str)
            or re.fullmatch(r"[0-9a-f]{40}", value["source_release"]) is None):
        raise UpgradeBlocked("invalid_source_release")
    hashes = value["migration_sha256"]
    if not isinstance(hashes, list) or len(hashes) != 2:
        raise UpgradeBlocked("unreviewed_migration_count")
    for digest in [value["source_schema_sha256"], *hashes]:
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise UpgradeBlocked("invalid_contract_digest")
    return value


def load_plan() -> dict[str, Any]:
    path = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"
    with path.open("rb") as handle:
        document = tomllib.load(handle)
    plan = validate_plan(document["tool"]["omnicio"]["timeweb"]["upgrade"])
    if document["project"]["version"] != plan["target_version"]:
        raise UpgradeBlocked("application_version_mismatch")
    return plan


def migration_bodies(plan: dict[str, Any], statements: list[str]) -> list[str]:
    validate_plan(plan)
    if len(statements) != 2:
        raise UpgradeBlocked("unreviewed_migration_count")
    result = []
    for source, expected in zip(statements, plan["migration_sha256"], strict=True):
        normalized = source.replace("\r\n", "\n")
        if _digest(normalized) != expected:
            raise UpgradeBlocked("migration_digest_mismatch")
        if not normalized.startswith("BEGIN;\n") or not normalized.endswith("\nCOMMIT;\n"):
            raise UpgradeBlocked("migration_transaction_contract_changed")
        result.append(normalized[len("BEGIN;\n"):-len("\nCOMMIT;\n")])
    return result


def schema_query(source: str, expected_digest: str | None = None) -> str:
    if expected_digest is not None and _digest(source) != expected_digest:
        raise UpgradeBlocked("source_schema_digest_mismatch")
    assignments = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "READINESS_QUERY"
                           for target in node.targets)]
    if len(assignments) != 1:
        raise UpgradeBlocked("invalid_readiness_contract")
    query = ast.literal_eval(assignments[0].value)
    if not isinstance(query, str) or not query.strip().startswith("SELECT"):
        raise UpgradeBlocked("invalid_readiness_contract")
    return query


def _private_file(path: pathlib.Path, maximum: int) -> str:
    details = path.lstat()
    if (not stat.S_ISREG(details.st_mode) or details.st_uid != 0
            or details.st_mode & 0o077 or not 0 < details.st_size <= maximum):
        raise UpgradeBlocked("untrusted_operational_file")
    return path.read_text(encoding="utf-8")


def parse_environment(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or name in result or re.fullmatch(r"[A-Z][A-Z0-9_]*", name) is None:
            raise UpgradeBlocked("invalid_runtime_environment")
        result[name] = value
    return result


def _read_receipt() -> dict[str, Any] | None:
    if not RECEIPT_PATH.exists() and not RECEIPT_PATH.is_symlink():
        return None
    value = json.loads(_private_file(RECEIPT_PATH, 16384))
    if not isinstance(value, dict):
        raise UpgradeBlocked("invalid_upgrade_receipt")
    return value


def _receipt_directory() -> pathlib.Path:
    directory = RECEIPT_PATH.parent
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    details = directory.lstat()
    if (not stat.S_ISDIR(details.st_mode) or details.st_uid != 0
            or details.st_mode & 0o077):
        raise UpgradeBlocked("untrusted_receipt_directory")
    return directory


@contextmanager
def _operation_lock() -> Iterator[None]:
    # Production runs on the one Linux VDS. Keep this import out of Windows CI.
    import fcntl

    path = _receipt_directory() / "operation.lock"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        details = os.fstat(descriptor)
        if (not stat.S_ISREG(details.st_mode) or details.st_uid != 0
                or details.st_mode & 0o077):
            raise UpgradeBlocked("untrusted_operation_lock")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise UpgradeBlocked("another_upgrade_is_running") from exc
        yield
    finally:
        os.close(descriptor)


def _write_receipt(value: dict[str, Any]) -> None:
    directory = _receipt_directory()
    temporary = RECEIPT_PATH.with_suffix(".pending")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(value, output, sort_keys=True, separators=(",", ":"), allow_nan=False)
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(RECEIPT_PATH)
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def operation_identity(plan: dict[str, Any], database: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_sha256": _digest(json.dumps(plan, sort_keys=True, separators=(",", ":"))),
        "database": database,
    }


def validate_receipt(receipt: dict[str, Any] | None, identity: dict[str, Any]) -> None:
    if receipt is None:
        return
    if (not isinstance(receipt, dict)
            or set(receipt) != {"identity", "phase", "release_sha", "installed_release"}
            or receipt["identity"] != identity or receipt["phase"] not in ("pending", "completed")):
        raise UpgradeBlocked("upgrade_receipt_mismatch")
    for name in ("release_sha", "installed_release"):
        if (not isinstance(receipt[name], str)
                or re.fullmatch(r"[0-9a-f]{40}", receipt[name]) is None):
            raise UpgradeBlocked("upgrade_receipt_mismatch")


def apply_upgrade(
    connection: Any, *, plan: dict[str, Any], statements: list[str], source_query: str,
    target_query: str, identity: dict[str, Any], receipt: dict[str, Any] | None,
    release_sha: str, installed_release: str, save_receipt: Callable[[dict[str, Any]], None],
) -> str:
    from psycopg.pq import TransactionStatus

    if not connection.autocommit or connection.info.transaction_status != TransactionStatus.IDLE:
        raise UpgradeBlocked("upgrade_requires_idle_autocommit_connection")
    bodies = migration_bodies(plan, statements)
    validate_receipt(receipt, identity)
    operation = {"identity": identity, "phase": "pending", "release_sha": release_sha,
                 "installed_release": installed_release}
    validate_receipt(operation, identity)
    result = "already_applied"
    with connection.transaction():
        connection.execute("SET LOCAL statement_timeout = '30s'")
        connection.execute("SET LOCAL lock_timeout = '5s'")
        connection.execute("SET LOCAL transaction_timeout = '60s'")
        locked = connection.execute("SELECT pg_try_advisory_xact_lock(4215095001300)").fetchone()
        if locked != (True,):
            raise UpgradeBlocked("another_upgrade_is_running")
        ready = connection.execute(target_query).fetchone() == (True,)
        if ready:
            if receipt is None:
                raise UpgradeBlocked("target_schema_has_no_operation_receipt")
        else:
            if installed_release != plan["source_release"]:
                raise UpgradeBlocked("initial_upgrade_requires_source_installation")
            _apply_pending(connection, bodies, source_query, target_query, receipt,
                           operation, save_receipt)
            result = "applied"
    # A lost write/SSH response leaves the pending receipt. The next invocation
    # first reads the target schema under the same lock; it does not repeat SQL.
    save_receipt({**operation, "phase": "completed"})
    return result


def _apply_pending(
    connection: Any, bodies: list[str], source_query: str, target_query: str,
    receipt: dict[str, Any] | None, operation: dict[str, Any],
    save_receipt: Callable[[dict[str, Any]], None],
) -> None:
    if receipt is not None and receipt["phase"] == "completed":
        raise UpgradeBlocked("completed_upgrade_schema_changed")
    if (connection.execute(source_query).fetchone() != (True,)
            or connection.execute(NEW_SCHEMA_ABSENT).fetchone() != (True,)):
        raise UpgradeBlocked("source_schema_is_not_reviewed_baseline")
    save_receipt(operation)
    for body in bodies:
        connection.execute(body)
    if connection.execute(target_query).fetchone() != (True,):
        raise UpgradeBlocked("target_schema_not_ready")


def _existing_installation(plan: dict[str, Any], receipt: dict[str, Any] | None,
                           release_sha: str) -> tuple[str, str]:
    from importlib.metadata import version

    current = CURRENT_RELEASE.resolve(strict=True)
    allowed = {plan["source_release"]}
    if receipt is not None:
        allowed.update({release_sha, receipt["release_sha"], receipt["installed_release"]})
    if current.parent != RELEASE_ROOT or current.name not in allowed:
        raise UpgradeBlocked("source_release_mismatch")
    expected = (plan["source_version"] if current.name == plan["source_release"]
                else plan["target_version"])
    if version("omnicio-gateway") != expected:
        raise UpgradeBlocked("installed_version_mismatch")
    baseline = RELEASE_ROOT / plan["source_release"] / "src/omnicio/schema.py"
    return (schema_query(baseline.read_text(encoding="utf-8"), plan["source_schema_sha256"]),
            current.name)


def _database_url(expected: dict[str, Any]) -> str:
    from psycopg.conninfo import conninfo_to_dict

    environment = parse_environment(_private_file(pathlib.Path("/etc/omnicio/runtime.env"), 65536))
    secrets = parse_environment(_private_file(pathlib.Path("/etc/omnicio/auth-secrets.env"), 65536))
    url = environment.get("DATABASE_URL", "")
    values = conninfo_to_dict(url)
    for name, key in (("host", "host"), ("port", "port"), ("dbname", "database"), ("user", "user")):
        if values.get(name) != str(expected[key]):
            raise UpgradeBlocked("runtime_database_identity_mismatch")
    password = secrets.get("OMNICIO_DB_ADMIN_PASSWORD")
    if not password or not values.get("password") or values["password"] != password:
        raise UpgradeBlocked("runtime_database_credentials_mismatch")
    for name in ("CLIENT_IP_KEY", "BROKER_TOKEN_CRYPTO_KEY", "VKID_FLOW_CRYPTO_KEY"):
        if not environment.get(name) or environment[name] != secrets.get(name):
            raise UpgradeBlocked("runtime_secret_mismatch")
    return url


def remote_main(payload: dict[str, Any]) -> None:
    import psycopg

    plan = validate_plan(payload["plan"])
    release_sha = payload["release_sha"]
    if not isinstance(release_sha, str) or re.fullmatch(r"[0-9a-f]{40}", release_sha) is None:
        raise UpgradeBlocked("invalid_target_release")
    migration_bodies(plan, payload["statements"])
    expected = payload["database"]
    url = _database_url(expected)
    with _operation_lock(), psycopg.connect(
        url, autocommit=True, connect_timeout=10,
        options="-c statement_timeout=30000 -c lock_timeout=5000 -c idle_session_timeout=60000",
    ) as connection:
        # This session lock survives COMMIT and protects both receipt reads and
        # writes. Closing this bounded connection releases it even on failure.
        if connection.execute("SELECT pg_try_advisory_lock(4215095001300)").fetchone() != (True,):
            raise UpgradeBlocked("another_upgrade_is_running")
        receipt = _read_receipt()
        identity = operation_identity(plan, expected)
        validate_receipt(receipt, identity)
        source_query, installed_release = _existing_installation(plan, receipt, release_sha)
        observed = connection.execute(
            "SELECT current_database(), current_user, inet_server_addr()::text, "
            "inet_server_port(), current_setting('server_version_num')::int, pg_is_in_recovery()",
        ).fetchone()
        if (observed is None or observed[:4] != (expected["database"], expected["user"],
                expected["host"], expected["port"]) or observed[4] // 10000 != 18 or observed[5]):
            raise UpgradeBlocked("connected_database_identity_mismatch")
        result = apply_upgrade(
            connection, plan=plan, statements=payload["statements"], source_query=source_query,
            target_query=payload["target_query"], identity=identity, receipt=receipt,
            release_sha=release_sha, installed_release=installed_release,
            save_receipt=_write_receipt,
        )
        if connection.execute(payload["target_query"]).fetchone() != (True,):
            raise UpgradeBlocked("committed_schema_not_ready")
    print(json.dumps({"status": result, "cluster_id": expected["cluster_id"],
                      "release_sha": release_sha, "new_database_copies": 0}))


def render_remote_upgrade(
    statements: list[str], *, release_sha: str, database: dict[str, Any],
) -> str:
    plan = load_plan()
    migration_bodies(plan, statements)
    source = pathlib.Path(__file__).read_text(encoding="utf-8")
    contract = pathlib.Path(__file__).resolve().parents[2] / "src/omnicio/schema.py"
    payload = {"plan": plan, "statements": statements, "release_sha": release_sha,
               "database": database,
               "target_query": schema_query(contract.read_text(encoding="utf-8"))}
    invocation = "\nimport sys\ntry:\n    remote_main(" + repr(payload) + ")\n"
    return source + invocation + '''except Exception as exc:
    if isinstance(exc, UpgradeBlocked):
        print("OMNICIO_UPGRADE: " + str(exc), file=sys.stderr)
    else:
        code = getattr(exc, "sqlstate", None)
        if isinstance(code, str) and re.fullmatch(r"[0-9A-Z]{5}", code):
            print("ERROR: " + code, file=sys.stderr)
        else:
            print("OMNICIO_UPGRADE: runtime_upgrade_failed", file=sys.stderr)
    raise SystemExit(1) from None
'''
