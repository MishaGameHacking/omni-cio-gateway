"""Reviewed in-place schema transitions in the existing database, without exporting rows.

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
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager, nullcontext
from datetime import UTC, datetime
from typing import Any, BinaryIO

MODE = "single_existing_database"
OPERATIONS = ("preflight", "email_probe", "apply")
RELEASE_SHA_PATTERN = r"[0-9a-f]{40}"
RECEIPT_PATH = pathlib.Path("/var/lib/omnicio-upgrade/1.5.0.json")
RELEASE_ROOT = pathlib.Path("/opt/omnicio/releases")
CURRENT_RELEASE = pathlib.Path("/opt/omnicio/current")
RECOVERY_DIRECTORY = pathlib.Path("/var/lib/omnicio-recovery")
# The existing exporter accepts at most 64 MiB before Fernet encryption.
MAX_LOGICAL_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_ENCRYPTED_ARCHIVE_BYTES = 2 * MAX_LOGICAL_ARCHIVE_BYTES
RECOVERY_FILES = {
    "status": (RECOVERY_DIRECTORY / "status.json", 16384, False),
    "manifest": (RECOVERY_DIRECTORY / "manifest.json", 16384, True),
    "archive": (RECOVERY_DIRECTORY / "database.dump.encrypted", MAX_ENCRYPTED_ARCHIVE_BYTES, True),
    "product_environment": (pathlib.Path("/etc/omnicio/product.env"), 65536, True),
}
CONFIGURATION_STAGES = (
    "not_started", "candidate_validation", "runtime_environment", "product_environment",
    "environment_merge", "settings_validation", "auth_email_validation", "push_validation",
    "email_readiness", "social_readiness", "validated",
)
CONFIGURATION_CUSTODY_FIELDS = ("existing_receipt_key_present", "existing_archive_key_present")
CONFIGURATION_SETTINGS_FIELDS = (
    "auth_smtp_host_present", "auth_smtp_sender_present", "market_data_token_present",
    "market_data_distribution_approved",
)
RECOVERY_STAGES = (
    "not_started", "system_identity_access", "status_file", "manifest_file", "encrypted_archive",
    "recovery_environment", "archive_decryption", "archive_format", "system_identity",
    "proof_verification", "verified",
)
# Only this reviewed verifier vocabulary can cross the operator-report boundary.
RECOVERY_PROOF_FAILURES = (
    "recovery_clock_unavailable", "recovery_source_identity_invalid", "recovery_state_mismatch",
    "recovery_proof_unverified", "recovery_source_mismatch", "recovery_source_stale",
    "recovery_manifest_unverified", "recovery_archive_mismatch",
)
CAPACITY_MEMORY_FIELDS = ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")
CAPACITY_OS_FIELDS = ("ID", "VERSION_ID", "VERSION_CODENAME")
MAX_OBSERVED_BYTES = 2**63 - 1
MAX_INSPECTION_REPORT_BYTES = 16384
AUTH_SERVICE = "omnicio-auth.service"
OBSERVER_TIMER = "omnicio-observer.timer"
OBSERVER_SERVICE = "omnicio-observer.service"
WRITER_UNITS = (AUTH_SERVICE, OBSERVER_TIMER, OBSERVER_SERVICE)
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
UPGRADE_1_4_SOURCE_QUERY = """
SELECT to_regclass('public.email_identities') IS NULL
    AND to_regclass('public.email_auth_challenges') IS NULL
    AND to_regclass('public.email_auth_rate_limits') IS NULL
    AND to_regclass('public.telegram_identities') IS NULL
    AND to_regclass('public.social_auth_flows') IS NULL
    AND (
        SELECT count(*) = 3 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'portfolio_snapshots'
          AND column_name IN ('nav_rub', 'rub_cash_total', 'rub_cash_blocked')
          AND data_type = 'numeric' AND numeric_precision = 24 AND numeric_scale = 8
          AND is_nullable = 'NO'
    )
    AND EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = to_regclass('public.sessions')
          AND conname = 'sessions_authentication_evidence'
          AND contype = 'c' AND convalidated AND conenforced
          AND regexp_replace(pg_get_expr(conbin, conrelid), '[[:space:]]+', '', 'g') =
              regexp_replace(
                  '(((authenticated_provider IS NULL) AND (authenticated_at IS NULL)) OR '
                  '((authenticated_provider IS NOT NULL) AND (authenticated_provider = ANY '
                  '(ARRAY[''vkid''::text, ''tid''::text])) AND (authenticated_at IS NOT NULL)))',
                  '[[:space:]]+', '', 'g'
              )
    )
"""


class UpgradeBlocked(RuntimeError):
    """A bounded diagnostic code; never include credentials, SQL or row values."""


def validate_operation(
    operation: str, *, release_sha: str | None, backup_only: bool = False,
) -> None:
    """Inspection is the default; mutations require an explicit accepted-main dispatch."""
    if operation not in OPERATIONS:
        raise UpgradeBlocked("invalid_postgres_operation")
    if backup_only:
        if operation != "preflight":
            raise UpgradeBlocked("scheduled_verification_cannot_apply")
        return
    if operation != "preflight" and (
        os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or not isinstance(release_sha, str)
        or re.fullmatch(RELEASE_SHA_PATTERN, release_sha) is None
        or os.environ.get("GITHUB_SHA") != release_sha
    ):
        raise UpgradeBlocked("postgres_operation_requires_manual_main")
    if operation == "email_probe" and os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise UpgradeBlocked("smtp_probe_requires_first_attempt")


def _digest(value: str) -> str:
    return hashlib.sha256(value.replace("\r\n", "\n").encode()).hexdigest()


def validate_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != PLAN_KEYS:
        raise UpgradeBlocked("invalid_upgrade_plan")
    transition = (value["source_version"], value["target_version"])
    if (value["mode"] != MODE
            or transition not in (("1.2.0", "1.3.0"), ("1.3.0", "1.4.0"),
                                  ("1.3.0", "1.5.0"))):
        raise UpgradeBlocked("unreviewed_version_transition")
    if (not isinstance(value["source_release"], str)
            or re.fullmatch(RELEASE_SHA_PATTERN, value["source_release"]) is None):
        raise UpgradeBlocked("invalid_source_release")
    hashes = value["migration_sha256"]
    expected_count = 3 if value["target_version"] == "1.5.0" else 2
    if not isinstance(hashes, list) or len(hashes) != expected_count:
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


def source_absence_query(plan: dict[str, Any]) -> str:
    """Reject partially applied migrations and drift outside the reviewed source schema."""
    validate_plan(plan)
    return (UPGRADE_1_4_SOURCE_QUERY if plan["target_version"] in {"1.4.0", "1.5.0"}
            else NEW_SCHEMA_ABSENT)


def migration_bodies(plan: dict[str, Any], statements: list[str]) -> list[str]:
    validate_plan(plan)
    if len(statements) != len(plan["migration_sha256"]):
        raise UpgradeBlocked("unreviewed_migration_count")
    result = []
    for index, (source, expected) in enumerate(zip(
        statements, plan["migration_sha256"], strict=True,
    )):
        normalized = source.replace("\r\n", "\n")
        if _digest(normalized) != expected:
            raise UpgradeBlocked("migration_digest_mismatch")
        if plan["target_version"] in {"1.4.0", "1.5.0"} and index == 1:
            # Accepted 0030 has no transaction wrapper. Its complete reviewed
            # digest is still mandatory; the controller owns the outer transaction.
            result.append(normalized)
            continue
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


def _trusted_operational_directory(details: os.stat_result) -> bool:
    return (stat.S_ISDIR(details.st_mode) and details.st_uid == 0
            and not details.st_mode & 0o022)


@contextmanager
def _operational_file(path: pathlib.Path, *, private: bool = True) -> Iterator[BinaryIO]:
    """Open one existing trusted inode for reading, without creating or following it."""
    if sys.platform != "linux":
        raise UpgradeBlocked("upgrade_requires_linux")
    parent = path.parent.lstat()
    if not _trusted_operational_directory(parent):
        raise UpgradeBlocked("untrusted_operational_directory")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as handle:
        details = os.fstat(handle.fileno())
        mask = 0o077 if private else 0o022
        if (not stat.S_ISREG(details.st_mode) or details.st_uid != 0
                or details.st_mode & mask):
            raise UpgradeBlocked("untrusted_operational_file")
        yield handle


def _operational_bytes(path: pathlib.Path, maximum: int, *, private: bool = True) -> bytes:
    """Read a bounded body from existing protected custody."""
    with _operational_file(path, private=private) as handle:
        details = os.fstat(handle.fileno())
        if not 0 < details.st_size <= maximum:
            raise UpgradeBlocked("untrusted_operational_file")
        body = handle.read(maximum + 1)
        if len(body) != details.st_size:
            raise UpgradeBlocked("operational_file_changed")
        return body


@contextmanager
def _inspection_lock(path: Any) -> Iterator[None]:
    """Share deployment serialization without creating the existing lock file."""
    if not isinstance(path, str):
        raise UpgradeBlocked("deployment_lock_unavailable")
    if sys.platform != "linux":
        raise UpgradeBlocked("upgrade_requires_linux")
    import fcntl

    lock_path = pathlib.Path(path)
    with ExitStack() as stack:
        try:
            handle = stack.enter_context(_operational_file(lock_path, private=False))
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            held, current = os.fstat(handle.fileno()), lock_path.lstat()
        except OSError as exc:
            raise UpgradeBlocked("deployment_lock_unavailable") from exc
        if (held.st_dev, held.st_ino) != (current.st_dev, current.st_ino):
            raise UpgradeBlocked("deployment_lock_changed")
        # Closing this descriptor also releases the lock after a timeout or error.
        yield


def _private_file(path: pathlib.Path, maximum: int) -> str:
    return _operational_bytes(path, maximum).decode("utf-8")


def _inspect_recovery_file(path: pathlib.Path) -> dict[str, Any]:
    """Observe metadata only; the recovery gate separately opens its trusted inode."""
    report: dict[str, Any] = {
        "state": "unavailable", "exists": None, "kind": None,
        "root_owned": None, "mode_octal": None, "size_bytes": None,
    }
    try:
        parent = path.parent.lstat()
    except FileNotFoundError:
        return report | {"state": "parent_missing", "exists": False}
    except OSError:
        return report
    if not _trusted_operational_directory(parent):
        return report | {"state": "parent_untrusted"}
    try:
        details = path.lstat()
    except FileNotFoundError:
        return report | {"state": "missing", "exists": False}
    except OSError:
        return report
    if not 0 <= details.st_size <= MAX_OBSERVED_BYTES:
        return report
    if stat.S_ISREG(details.st_mode):
        kind = "regular"
    elif stat.S_ISLNK(details.st_mode):
        kind = "symlink"
    else:
        kind = "other"
    return {
        "state": "observed", "exists": True, "kind": kind,
        "root_owned": details.st_uid == 0,
        "mode_octal": format(stat.S_IMODE(details.st_mode), "04o"),
        "size_bytes": details.st_size,
    }


def inspect_host_capacity() -> dict[str, Any]:
    """Observe current host resources without assigning load or price thresholds."""
    import shutil

    try:
        memory: dict[str, int | None] = dict.fromkeys(CAPACITY_MEMORY_FIELDS)
        with pathlib.Path("/proc/meminfo").open(encoding="utf-8") as handle:
            raw_memory = handle.read(65537)
        with pathlib.Path("/etc/os-release").open(encoding="utf-8") as handle:
            raw_release = handle.read(65537)
        if len(raw_memory) > 65536 or len(raw_release) > 65536:
            raise ValueError("host_capacity_unavailable")
        for line in raw_memory.splitlines():
            key, separator, value = line.partition(":")
            if not separator or key not in CAPACITY_MEMORY_FIELDS:
                continue
            amount, unit = value.split()
            if unit != "kB":
                raise ValueError("host_capacity_unavailable")
            memory[key] = int(amount) * 1024
        release = {}
        for line in raw_release.splitlines():
            key, separator, value = line.partition("=")
            if separator and key in CAPACITY_OS_FIELDS:
                release[key] = value.strip('"')
        disk = shutil.disk_usage("/var/lib")
        report = {
            "status": "observed", "cpu_count": os.cpu_count(), "memory_bytes": memory,
            "disk_total_bytes": disk.total, "disk_free_bytes": disk.free,
            "os": release, "systemd_run": bool(shutil.which("systemd-run")),
            "postgres_majors": sorted(
                path.name for path in pathlib.Path("/usr/lib/postgresql").glob("*")
                if path.is_dir() and path.name.isdecimal()
            ),
        }
        if _valid_host_capacity(report):
            return report
    except (OSError, ValueError, TypeError):
        pass
    return {"status": "unavailable", "code": "host_capacity_unavailable"}


def _observed_integer(value: Any, *, minimum: int = 0) -> bool:
    return type(value) is int and minimum <= value <= MAX_OBSERVED_BYTES


def _valid_host_capacity(value: Any) -> bool:
    if value == {"status": "unavailable", "code": "host_capacity_unavailable"}:
        return True
    if (not isinstance(value, dict) or set(value) != {
            "status", "cpu_count", "memory_bytes", "disk_total_bytes", "disk_free_bytes",
            "os", "systemd_run", "postgres_majors",
    } or value.get("status") != "observed"
            or (value["cpu_count"] is not None
                and not _observed_integer(value["cpu_count"], minimum=1))
            or not _observed_integer(value["disk_total_bytes"])
            or not _observed_integer(value["disk_free_bytes"])
            or value["disk_free_bytes"] > value["disk_total_bytes"]
            or type(value["systemd_run"]) is not bool):
        return False
    memory, release, majors = value["memory_bytes"], value["os"], value["postgres_majors"]
    if (not isinstance(memory, dict) or set(memory) != set(CAPACITY_MEMORY_FIELDS)
            or any(item is not None and not _observed_integer(item) for item in memory.values())
            or not isinstance(release, dict) or not set(release).issubset(CAPACITY_OS_FIELDS)
            or any(not isinstance(item, str) or re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", item) is None
                   for item in release.values())
            or not isinstance(majors, list) or len(majors) > 32
            or any(not isinstance(item, str)
                   or re.fullmatch(r"\d{1,3}", item, flags=re.ASCII) is None
                   for item in majors)):
        return False
    for free, total in (("MemAvailable", "MemTotal"), ("SwapFree", "SwapTotal")):
        if memory[free] is not None and memory[total] is not None and memory[free] > memory[total]:
            return False
    return majors == sorted(set(majors))


def _unescape_environment_text(text: str) -> str:
    """Decode the four escapes permitted inside the writer's double quotes."""
    result = []
    index = 0
    while index < len(text):
        character = text[index]
        if character == "\\":
            index += 1
            if index == len(text) or text[index] not in '\\"$`':
                raise UpgradeBlocked("invalid_runtime_environment")
            character = text[index]
        elif character in '"$`':
            raise UpgradeBlocked("invalid_runtime_environment")
        result.append(character)
        index += 1
    return "".join(result)


def _environment_text(value: str) -> str:
    """Decode only the project's quoted writer grammar, without shell evaluation."""
    if value.startswith("'"):
        if not value.endswith("'") or len(value) < 2 or "'" in value[1:-1]:
            raise UpgradeBlocked("invalid_runtime_environment")
        return value[1:-1]
    if not value.startswith('"'):
        if any(character.isspace() or character in "\\\"'$`;&|<>()[]{}#~*"
               for character in value):
            raise UpgradeBlocked("invalid_runtime_environment")
        return value
    if not value.endswith('"') or len(value) < 2:
        raise UpgradeBlocked("invalid_runtime_environment")
    return _unescape_environment_text(value[1:-1])


def parse_environment(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        if not separator or name in result or re.fullmatch(r"[A-Z][A-Z0-9_]*", name) is None:
            raise UpgradeBlocked("invalid_runtime_environment")
        result[name] = _environment_text(value)
    return result


def _require_recovery(
    connection: Any, plan: dict[str, Any], expected: dict[str, Any],
    validator: Callable[..., dict[str, Any]],
    *, diagnostics: dict[str, Any] | None = None,
) -> None:
    """Authenticate and decrypt only existing evidence in protected server custody."""
    from cryptography.fernet import Fernet, InvalidToken

    observation = {} if diagnostics is None else diagnostics
    observation.update({
        "stage": "system_identity_access", "proof_code": "not_checked",
        "system_identity_access": None, "system_identity_read": False,
    })
    try:
        has_access = connection.execute(
            "SELECT pg_catalog.has_function_privilege(current_user, "
            "'pg_catalog.pg_control_system()', 'EXECUTE')",
        ).fetchone() == (True,)
        observation["system_identity_access"] = has_access
        if not has_access:
            raise UpgradeBlocked("recovery_system_identity_access_unavailable")
        observation["stage"] = "status_file"
        state = json.loads(_recovery_file_bytes("status"))
        observation["stage"] = "manifest_file"
        manifest = json.loads(_recovery_file_bytes("manifest").decode("utf-8"))
        observation["stage"] = "encrypted_archive"
        encrypted = _recovery_file_bytes("archive")
        observation["stage"] = "recovery_environment"
        environment = parse_environment(_recovery_file_bytes("product_environment").decode("utf-8"))
        observation["stage"] = "archive_decryption"
        raw = Fernet(environment.get("OMNICIO_RESTORE_ARCHIVE_KEY", "")).decrypt(encrypted)
        observation["stage"] = "archive_format"
        if not raw.startswith(b"PGDMP") or not 0 < len(raw) <= MAX_LOGICAL_ARCHIVE_BYTES:
            raise UpgradeBlocked("recovery_archive_invalid")
        observation["stage"] = "system_identity"
        system_id = connection.execute(
            "SELECT system_identifier::text FROM pg_catalog.pg_control_system()",
        ).fetchone()
        if system_id is None:
            raise UpgradeBlocked("recovery_database_identity_missing")
        observation["system_identity_read"] = True
        observation["stage"] = "proof_verification"
        try:
            validator(
                state, environment.get("OMNICIO_RESTORE_RECEIPT_KEY", ""),
                cluster_id=expected["cluster_id"], source_release=plan["source_release"],
                source_system_id=system_id[0], now=datetime.now(UTC), manifest=manifest,
                encrypted_archive_sha256=hashlib.sha256(encrypted).hexdigest(),
                decrypted_archive_sha256=hashlib.sha256(raw).hexdigest(),
            )
        except (ValueError, TypeError) as exc:
            observation["proof_code"] = (
                str(exc) if isinstance(exc, ValueError) and str(exc) in RECOVERY_PROOF_FAILURES
                else "proof_invalid"
            )
            raise
        observation.update({"stage": "verified", "proof_code": "verified"})
    except (OSError, ValueError, TypeError, InvalidToken) as exc:
        # Ciphertext, plaintext, keys, paths supplied by another actor and SQL
        # driver diagnostics never become a recovery failure message.
        raise UpgradeBlocked("upgrade_recovery_unavailable") from exc


def _recovery_file_bytes(name: str) -> bytes:
    path, maximum, private = RECOVERY_FILES[name]
    return _operational_bytes(path, maximum, private=private)


def render_source_definitions(path: pathlib.Path, names: set[str]) -> str:
    """Emit each requested module-level definition exactly once, in source order."""
    source = path.read_text(encoding="utf-8")
    definitions: dict[str, str] = {}
    for node in ast.parse(source).body:
        name = None
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            name = node.name
        elif (isinstance(node, ast.Assign) and len(node.targets) == 1
              and isinstance(node.targets[0], ast.Name)):
            name = node.targets[0].id
        if name in names:
            segment = ast.get_source_segment(source, node)
            if segment is None or name in definitions:
                raise UpgradeBlocked("source_definition_contract_changed")
            definitions[name] = segment
    if set(definitions) != names:
        raise UpgradeBlocked("source_definition_contract_changed")
    return "\n\n".join(definitions.values()) + "\n"


def render_recovery_validator() -> str:
    """Ship the canonical verifier definitions without importing the old installed module."""
    path = pathlib.Path(__file__).resolve().parents[2] / "src/omnicio/recovery.py"
    names = {
        "BACKUP_MAX_AGE", "RESTORE_MAX_AGE", "RESTORE_CHECKS", "SHA256_PATTERN", "LOGICAL_SOURCES",
        "sign_recovery_evidence",
        "verified_recovery_evidence", "_restore_verification", "_timestamp",
        "require_upgrade_recovery", "_require_upgrade_archive",
    }
    return ("\nimport hmac\nfrom datetime import timedelta\n\n"
            + render_source_definitions(path, names))


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
    if sys.platform != "linux":
        raise UpgradeBlocked("upgrade_requires_linux")
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
    if sys.platform != "linux":
        raise UpgradeBlocked("upgrade_requires_linux")
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
    keys = {"identity", "phase", "release_sha", "installed_release"}
    if (not isinstance(receipt, dict) or set(receipt) not in (keys, keys | {"writers"})
            or receipt["identity"] != identity or receipt["phase"] not in ("pending", "completed")):
        raise UpgradeBlocked("upgrade_receipt_mismatch")
    for name in ("release_sha", "installed_release"):
        if (not isinstance(receipt[name], str)
                or re.fullmatch(RELEASE_SHA_PATTERN, receipt[name]) is None):
            raise UpgradeBlocked("upgrade_receipt_mismatch")
    if "writers" in receipt:
        _validate_writer_state(receipt["writers"])


def _validate_writer_state(state: Any) -> None:
    if not isinstance(state, dict) or set(state) != set(WRITER_UNITS):
        raise UpgradeBlocked("upgrade_writer_receipt_mismatch")
    for value in state.values():
        if (not isinstance(value, dict) or set(value) != {"active", "enabled"}
                or type(value["active"]) is not bool
                or value["enabled"] not in ("enabled", "disabled", "static")):
            raise UpgradeBlocked("upgrade_writer_receipt_mismatch")


def _unit_state(command: str, unit: str) -> str:
    result = subprocess.run(
        ["systemctl", "--no-ask-password", command, unit], check=False,
        capture_output=True, text=True, timeout=10,
    )
    value = result.stdout.strip()
    allowed = ({"active", "inactive", "failed"} if command == "is-active"
               else {"enabled", "disabled", "static"})
    if result.returncode not in (0, 1, 3) or value not in allowed:
        raise UpgradeBlocked("upgrade_writer_state_unknown")
    return value


def _capture_writer_state() -> dict[str, dict[str, Any]]:
    state = {unit: {"active": _unit_state("is-active", unit) == "active",
                    "enabled": _unit_state("is-enabled", unit)} for unit in WRITER_UNITS}
    if not state[AUTH_SERVICE]["active"]:
        raise UpgradeBlocked("source_application_not_running")
    return state


def _change_units(command: str, units: list[str]) -> None:
    if not units:
        return
    result = subprocess.run(
        ["systemctl", "--no-ask-password", command, *units], check=False,
        capture_output=True, timeout=60,
    )
    if result.returncode != 0:
        raise UpgradeBlocked("upgrade_writer_change_unconfirmed")


def _assert_writers_stopped() -> None:
    for unit in WRITER_UNITS:
        if (_unit_state("is-active", unit) == "active"
                or _unit_state("is-enabled", unit) == "enabled"):
            raise UpgradeBlocked("upgrade_writer_stop_unconfirmed")


def _drain_writers(state: dict[str, dict[str, Any]]) -> None:
    _validate_writer_state(state)
    # Persistently disable the previous runtime before stopping it so a reboot
    # after COMMIT cannot start a 1.3 reader against nullable 1.4 snapshots.
    _change_units("disable", [unit for unit in WRITER_UNITS
                              if state[unit]["enabled"] == "enabled"])
    _change_units("stop", [OBSERVER_TIMER, OBSERVER_SERVICE, AUTH_SERVICE])
    _assert_writers_stopped()


def _restore_writers(state: dict[str, dict[str, Any]]) -> None:
    _validate_writer_state(state)
    _change_units("enable", [unit for unit in WRITER_UNITS
                             if state[unit]["enabled"] == "enabled"])
    _change_units("start", [unit for unit in WRITER_UNITS if state[unit]["active"]])
    for unit in WRITER_UNITS:
        if (_unit_state("is-enabled", unit) != state[unit]["enabled"]
                or (unit != OBSERVER_SERVICE
                    and (_unit_state("is-active", unit) == "active") != state[unit]["active"])):
            raise UpgradeBlocked("source_writer_resume_unconfirmed")


def apply_upgrade(
    connection: Any, *, plan: dict[str, Any], statements: list[str], source_query: str,
    target_query: str, identity: dict[str, Any], receipt: dict[str, Any] | None,
    release_sha: str, installed_release: str, save_receipt: Callable[[dict[str, Any]], None],
    require_recovery: Callable[[], None] | None = None,
) -> str:
    from psycopg.pq import TransactionStatus

    if not connection.autocommit or connection.info.transaction_status != TransactionStatus.IDLE:
        raise UpgradeBlocked("upgrade_requires_idle_autocommit_connection")
    bodies = migration_bodies(plan, statements)
    validate_receipt(receipt, identity)
    operation = {"identity": identity, "phase": "pending", "release_sha": release_sha,
                 "installed_release": installed_release}
    if receipt is not None and "writers" in receipt:
        operation["writers"] = receipt["writers"]
    validate_receipt(operation, identity)
    result = "already_applied"
    with connection.transaction():
        # Reviewed migrations use unqualified table names. Explicitly pin
        # their namespace before checking and changing the public schema.
        connection.execute("SET LOCAL search_path TO public, pg_temp")
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
                           operation, save_receipt, source_absence_query(plan),
                           require_recovery, plan["target_version"] in {"1.4.0", "1.5.0"})
            result = "applied"
    # A lost write/SSH response leaves the pending receipt. The next invocation
    # first reads the target schema under the same lock; it does not repeat SQL.
    save_receipt({**operation, "phase": "completed"})
    return result


def _apply_pending(
    connection: Any, bodies: list[str], source_query: str, target_query: str,
    receipt: dict[str, Any] | None, operation: dict[str, Any],
    save_receipt: Callable[[dict[str, Any]], None],
    source_absent: str, require_recovery: Callable[[], None] | None, recovery_required: bool,
) -> None:
    if receipt is not None and receipt["phase"] == "completed":
        raise UpgradeBlocked("completed_upgrade_schema_changed")
    if (connection.execute(source_query).fetchone() != (True,)
            or connection.execute(source_absent).fetchone() != (True,)):
        raise UpgradeBlocked("source_schema_is_not_reviewed_baseline")
    if recovery_required:
        if require_recovery is None:
            raise UpgradeBlocked("upgrade_recovery_required")
        require_recovery()
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


def _verify_connected_database(connection: Any, expected: dict[str, Any]) -> None:
    """Verify the live database before any migration or operation receipt write."""
    # An explicit inet::text cast retains /32 (or /128). host() returns the
    # address itself, matching the exact private endpoint supplied by Timeweb.
    observed = connection.execute(
        "SELECT current_database(), current_user, host(inet_server_addr()), "
        "inet_server_port(), current_setting('server_version_num')::int, pg_is_in_recovery()",
    ).fetchone()
    if observed is None:
        raise UpgradeBlocked("connected_database_observation_missing")
    fields = (("name", "database"), ("user", "user"), ("address", "host"), ("port", "port"))
    for actual, (label, key) in zip(observed[:4], fields, strict=True):
        if actual != expected[key]:
            # Report the failed invariant, never SQL results or credentials.
            raise UpgradeBlocked(f"connected_database_{label}_mismatch")
    if observed[4] // 10000 != 18:
        raise UpgradeBlocked("connected_database_version_mismatch")
    if observed[5]:
        raise UpgradeBlocked("connected_database_recovery_mismatch")


def _verify_upgrade_role(connection: Any) -> None:
    observed = connection.execute(
        "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls "
        "FROM pg_catalog.pg_roles WHERE rolname = current_user",
    ).fetchone()
    if observed != (False, False, False, False, False):
        raise UpgradeBlocked("upgrade_database_role_is_privileged")


def _source_is_ready(connection: Any, plan: dict[str, Any], source_query: str) -> bool:
    return bool(connection.execute(source_query).fetchone() == (True,)
                and connection.execute(source_absence_query(plan)).fetchone() == (True,))


def _resume_source_after_failure(
    url: str, expected: dict[str, Any], plan: dict[str, Any], source_query: str,
    writers: dict[str, dict[str, Any]],
) -> bool:
    """Reconnect to prove rollback; never restart 1.3 after COMMIT or uncertain state."""
    import psycopg

    try:
        with psycopg.connect(
            url, autocommit=True, connect_timeout=10,
            options="-c statement_timeout=30000 -c lock_timeout=5000 "
                    "-c idle_session_timeout=60000 -c search_path=public,pg_temp",
        ) as verification:
            if verification.execute(
                "SELECT pg_try_advisory_lock(4215095001300)",
            ).fetchone() != (True,):
                return False
            if CURRENT_RELEASE.resolve(strict=True) != RELEASE_ROOT / plan["source_release"]:
                return False
            _verify_connected_database(verification, expected)
            _verify_upgrade_role(verification)
            with verification.transaction():
                verification.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                if not _source_is_ready(verification, plan, source_query):
                    return False
            _restore_writers(writers)
            return True
    except (UpgradeBlocked, OSError, ValueError, psycopg.Error, subprocess.SubprocessError):
        return False


def _current_schema_ready(
    connection: Any, *, payload: dict[str, Any], plan: dict[str, Any],
    receipt: dict[str, Any] | None,
    source_query: str, installed_release: str,
) -> bool:
    _verify_upgrade_role(connection)
    ready = bool(connection.execute(payload["target_query"]).fetchone() == (True,))
    if ready:
        if receipt is None or "writers" not in receipt:
            raise UpgradeBlocked("target_schema_has_no_operation_receipt")
        # A completed/ambiguous first cutover may still have the source symlink.
        # It must remain stopped until the accepted 1.4 application is promoted.
        if installed_release == plan["source_release"]:
            _assert_writers_stopped()
    else:
        if installed_release != plan["source_release"]:
            raise UpgradeBlocked("initial_upgrade_requires_source_installation")
        if receipt is not None and receipt["phase"] == "completed":
            raise UpgradeBlocked("completed_upgrade_schema_changed")
        if not _source_is_ready(connection, plan, source_query):
            raise UpgradeBlocked("source_schema_is_not_reviewed_baseline")
    return ready


def _current_preflight(
    connection: Any, *, payload: dict[str, Any], plan: dict[str, Any],
    receipt: dict[str, Any] | None,
    source_query: str, installed_release: str,
    recovery_validator: Callable[..., dict[str, Any]],
    product_preflight: Callable[[], dict[str, Any]],
) -> bool:
    ready = _current_schema_ready(
        connection, payload=payload, plan=plan, receipt=receipt,
        source_query=source_query, installed_release=installed_release,
    )
    if not ready:
        # These checks neither create files nor touch systemd. Missing or stale
        # evidence and incomplete effective email configuration preserve 1.3.
        _require_recovery(connection, plan, payload["database"], recovery_validator)
        product_preflight()
    return ready


def _inspection_failure(exc: Exception, component: str) -> dict[str, str]:
    code = f"{component}_inspection_failed"
    if isinstance(exc, UpgradeBlocked) and re.fullmatch(r"[a-z_]{1,64}", str(exc)):
        code = str(exc)
    return {"status": "blocked", "code": code}


def _inspection_diagnostics() -> dict[str, Any]:
    return {
        "configuration": {
            "stage": "not_started",
            **dict.fromkeys((*CONFIGURATION_CUSTODY_FIELDS, *CONFIGURATION_SETTINGS_FIELDS)),
        },
        "recovery": {
            "stage": "not_started", "proof_code": "not_checked",
            "system_identity_access": None, "system_identity_read": False,
        },
        "files": {name: _inspect_recovery_file(specification[0])
                  for name, specification in RECOVERY_FILES.items()},
        "host": inspect_host_capacity(),
    }


def _valid_configuration_observation(value: Any) -> bool:
    keys = {"stage", *CONFIGURATION_CUSTODY_FIELDS, *CONFIGURATION_SETTINGS_FIELDS}
    if (not isinstance(value, dict) or set(value) != keys
            or value["stage"] not in CONFIGURATION_STAGES):
        return False
    stage = CONFIGURATION_STAGES.index(value["stage"])
    for names, first_stage in (
        (CONFIGURATION_CUSTODY_FIELDS, "environment_merge"),
        (CONFIGURATION_SETTINGS_FIELDS, "auth_email_validation"),
    ):
        observed = stage >= CONFIGURATION_STAGES.index(first_stage)
        if any(type(value[name]) is not bool if observed else value[name] is not None
               for name in names):
            return False
    if value["stage"] == "validated":
        return (value["auth_smtp_host_present"] is True
                and value["auth_smtp_sender_present"] is True)
    return True


def _valid_recovery_observation(value: Any) -> bool:
    if (not isinstance(value, dict) or set(value) != {
            "stage", "proof_code", "system_identity_access", "system_identity_read",
    } or value["stage"] not in RECOVERY_STAGES
            or value["proof_code"] not in ("not_checked", "verified", "proof_invalid",
                                            *RECOVERY_PROOF_FAILURES)
            or (value["system_identity_access"] is not None
                and type(value["system_identity_access"]) is not bool)
            or type(value["system_identity_read"]) is not bool):
        return False
    if (value["stage"] not in ("not_started", "system_identity_access")
            and value["system_identity_access"] is not True):
        return False
    if value["stage"] == "not_started" and value["system_identity_access"] is not None:
        return False
    if value["stage"] == "system_identity_access" and value["system_identity_access"] is True:
        return False
    identity_read = value["stage"] in ("proof_verification", "verified")
    if value["system_identity_read"] != identity_read:
        return False
    if value["stage"] == "verified":
        return bool(value["proof_code"] == "verified")
    return value["proof_code"] != "verified" and (
        identity_read or value["proof_code"] == "not_checked"
    )


def _valid_file_observation(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "state", "exists", "kind", "root_owned", "mode_octal", "size_bytes",
    }:
        return False
    state = value["state"]
    if state == "observed":
        return (value["exists"] is True and value["kind"] in ("regular", "symlink", "other")
                and type(value["root_owned"]) is bool
                and isinstance(value["mode_octal"], str)
                and re.fullmatch(r"[0-7]{4}", value["mode_octal"]) is not None
                and _observed_integer(value["size_bytes"]))
    if state not in ("missing", "parent_missing", "parent_untrusted", "unavailable"):
        return False
    exists = False if state in ("missing", "parent_missing") else None
    return value["exists"] is exists and all(
        value[name] is None for name in ("kind", "root_owned", "mode_octal", "size_bytes")
    )


def valid_inspection_diagnostics(
    value: Any, *, recovery_ready: bool, configuration_ready: bool,
) -> bool:
    """Accept only the fixed operator vocabulary; observations never grant readiness."""
    if not isinstance(value, dict) or set(value) != {"configuration", "recovery", "files", "host"}:
        return False
    configuration, recovery, files = value["configuration"], value["recovery"], value["files"]
    return (
        _valid_configuration_observation(configuration) and _valid_recovery_observation(recovery)
        and configuration_ready == (configuration["stage"] == "validated")
        and recovery_ready == (recovery["stage"] == "verified")
        and isinstance(files, dict) and set(files) == set(RECOVERY_FILES)
        and all(_valid_file_observation(item) for item in files.values())
        and _valid_host_capacity(value["host"])
    )


def _inspect_email_probe(
    operation: str, configuration: dict[str, Any],
    smtp_probe: Callable[[], dict[str, Any]] | None,
) -> dict[str, Any]:
    if operation != "email_probe":
        return {"status": "not_requested", "code": "not_requested", "message_id": ""}
    if configuration["status"] != "configuration_ready" or smtp_probe is None:
        return {"status": "blocked", "code": "product_configuration_invalid", "message_id": ""}
    try:
        return smtp_probe()
    except (UpgradeBlocked, OSError, ValueError) as exc:
        return {**_inspection_failure(exc, "smtp"), "message_id": ""}


def _inspect_current_upgrade(
    connection: Any, *, payload: dict[str, Any], plan: dict[str, Any],
    receipt: dict[str, Any] | None, source_query: str, installed_release: str,
    recovery_validator: Callable[..., dict[str, Any]] | None,
    product_preflight: Callable[..., dict[str, Any]] | None,
    smtp_probe: Callable[[], dict[str, Any]] | None,
) -> dict[str, Any]:
    """Read both live prerequisites independently, without entering the mutation path."""
    import psycopg

    if recovery_validator is None or product_preflight is None:
        raise UpgradeBlocked("upgrade_preflight_missing")
    ready = _current_schema_ready(
        connection, payload=payload, plan=plan, receipt=receipt,
        source_query=source_query, installed_release=installed_release,
    )
    diagnostics = _inspection_diagnostics()
    try:
        _require_recovery(connection, plan, payload["database"], recovery_validator,
                          diagnostics=diagnostics["recovery"])
        recovery = {"status": "ready", "code": "recovery_verified"}
    except (UpgradeBlocked, OSError, ValueError, TypeError, psycopg.Error) as exc:
        recovery = _inspection_failure(exc, "recovery")
    try:
        configuration = product_preflight(diagnostics=diagnostics["configuration"])
    except (UpgradeBlocked, OSError, ValueError, TypeError) as exc:
        configuration = _inspection_failure(exc, "configuration")
    probe = _inspect_email_probe(payload["operation"], configuration, smtp_probe)
    preflight_ready = (recovery["status"] == "ready"
                       and configuration["status"] == "configuration_ready"
                       and probe["status"] in {"not_requested", "accepted"})
    return {
        "status": "preflight_ready" if preflight_ready else "preflight_blocked",
        "operation": payload["operation"], "release_sha": payload["release_sha"],
        "cluster_id": payload["database"]["cluster_id"], "new_database_copies": 0,
        "schema": "target_ready" if ready else "source_ready",
        "recovery": recovery, "configuration": configuration, "email_probe": probe,
        "diagnostics": diagnostics,
    }


def _apply_current_upgrade(
    connection: Any, *, payload: dict[str, Any], plan: dict[str, Any], url: str,
    identity: dict[str, Any], receipt: dict[str, Any] | None,
    source_query: str, installed_release: str,
    recovery_validator: Callable[..., dict[str, Any]] | None,
    product_preflight: Callable[[], dict[str, Any]] | None,
) -> str:
    import psycopg

    if recovery_validator is None or product_preflight is None:
        raise UpgradeBlocked("upgrade_preflight_missing")
    ready = _current_preflight(
        connection, payload=payload, plan=plan, receipt=receipt, source_query=source_query,
        installed_release=installed_release, recovery_validator=recovery_validator,
        product_preflight=product_preflight,
    )

    with _operation_lock():
        if not ready:
            if not _source_is_ready(connection, plan, source_query):
                raise UpgradeBlocked("source_schema_is_not_reviewed_baseline")
            if receipt is None:
                receipt = {"identity": identity, "phase": "pending",
                           "release_sha": payload["release_sha"],
                           "installed_release": installed_release,
                           "writers": _capture_writer_state()}
                validate_receipt(receipt, identity)
                _write_receipt(receipt)
        if receipt is None or "writers" not in receipt:
            raise UpgradeBlocked("upgrade_writer_receipt_mismatch")
        try:
            if not ready:
                _drain_writers(receipt["writers"])
            result = apply_upgrade(
                connection, plan=plan, statements=payload["statements"], source_query=source_query,
                target_query=payload["target_query"], identity=identity, receipt=receipt,
                release_sha=payload["release_sha"], installed_release=installed_release,
                save_receipt=_write_receipt,
                require_recovery=lambda: _require_recovery(
                    connection, plan, payload["database"], recovery_validator,
                ),
            )
            if connection.execute(payload["target_query"]).fetchone() != (True,):
                raise UpgradeBlocked("committed_schema_not_ready")
        except (UpgradeBlocked, OSError, ValueError, psycopg.Error,
                subprocess.SubprocessError) as exc:
            connection.close()
            if (not ready and not _resume_source_after_failure(
                url, payload["database"], plan, source_query, receipt["writers"],
            )):
                raise UpgradeBlocked("upgrade_failed_writers_remain_stopped") from exc
            raise
    return result


def remote_main(
    payload: dict[str, Any], *, recovery_validator: Callable[..., dict[str, Any]] | None = None,
    product_preflight: Callable[..., dict[str, Any]] | None = None,
    smtp_probe: Callable[[], dict[str, Any]] | None = None,
) -> None:
    if sys.platform != "linux":
        raise UpgradeBlocked("upgrade_requires_linux")
    import psycopg

    plan = validate_plan(payload["plan"])
    if payload.get("application_version") != plan["target_version"]:
        raise UpgradeBlocked("application_version_mismatch")
    # The historical fixture predates staged inspection. Current release payloads
    # always include an explicit operation and otherwise remain read-only.
    operation = payload.get("operation", "apply" if plan["target_version"] == "1.3.0"
                            else "preflight")
    if operation not in OPERATIONS:
        raise UpgradeBlocked("invalid_postgres_operation")
    payload = {**payload, "operation": operation}
    release_sha = payload["release_sha"]
    if not isinstance(release_sha, str) or re.fullmatch(RELEASE_SHA_PATTERN, release_sha) is None:
        raise UpgradeBlocked("invalid_target_release")
    migration_bodies(plan, payload["statements"])
    expected = payload["database"]
    lock = (_inspection_lock(payload.get("deployment_lock"))
            if operation != "apply" else nullcontext())
    with lock:
        url = _database_url(expected)
        options = ("-c statement_timeout=30000 -c lock_timeout=5000 "
                   "-c idle_session_timeout=60000 -c search_path=public,pg_temp")
        if operation != "apply":
            options += " -c default_transaction_read_only=on"
        with psycopg.connect(
            url, autocommit=True, connect_timeout=10,
            options=options,
        ) as connection:
            # This session lock survives COMMIT and protects both receipt reads and
            # writes. Closing this bounded connection releases it even on failure.
            if connection.execute(
                "SELECT pg_try_advisory_lock(4215095001300)",
            ).fetchone() != (True,):
                raise UpgradeBlocked("another_upgrade_is_running")
            receipt = _read_receipt()
            identity = operation_identity(plan, expected)
            validate_receipt(receipt, identity)
            source_query, installed_release = _existing_installation(plan, receipt, release_sha)
            _verify_connected_database(connection, expected)
            if operation != "apply":
                report = _inspect_current_upgrade(
                    connection, payload=payload, plan=plan, receipt=receipt,
                    source_query=source_query, installed_release=installed_release,
                    recovery_validator=recovery_validator, product_preflight=product_preflight,
                    smtp_probe=smtp_probe,
                )
                print(json.dumps(report))
                return
            if plan["target_version"] in {"1.4.0", "1.5.0"}:
                result = _apply_current_upgrade(
                    connection, payload=payload, plan=plan, url=url, identity=identity,
                    receipt=receipt, source_query=source_query, installed_release=installed_release,
                    recovery_validator=recovery_validator, product_preflight=product_preflight,
                )
            else:
                with _operation_lock():
                    result = apply_upgrade(
                        connection, plan=plan, statements=payload["statements"],
                        source_query=source_query, target_query=payload["target_query"],
                        identity=identity, receipt=receipt, release_sha=release_sha,
                        installed_release=installed_release, save_receipt=_write_receipt,
                    )
            if connection.execute(payload["target_query"]).fetchone() != (True,):
                raise UpgradeBlocked("committed_schema_not_ready")
        print(json.dumps({"status": result, "cluster_id": expected["cluster_id"],
                          "release_sha": release_sha, "new_database_copies": 0}))


def render_remote_upgrade(
    statements: list[str], *, release_sha: str, database: dict[str, Any],
    operation: str = "preflight",
) -> str:
    from timeweb_auth_app import DEPLOY_LOCK, render_product_preflight

    validate_operation(operation, release_sha=release_sha)
    plan = load_plan()
    migration_bodies(plan, statements)
    root = pathlib.Path(__file__).resolve().parents[2]
    with (root / "pyproject.toml").open("rb") as handle:
        application_version = tomllib.load(handle)["project"]["version"]
    if application_version != plan["target_version"]:
        raise UpgradeBlocked("application_version_mismatch")
    source = (pathlib.Path(__file__).read_text(encoding="utf-8")
              + render_recovery_validator() + render_product_preflight(
                  smtp_probe=operation == "email_probe", release_sha=release_sha,
                  capture_configuration_errors=operation != "apply",
              ))
    contract = root / "src/omnicio/schema.py"
    payload = {"plan": plan, "statements": statements, "release_sha": release_sha,
               "database": database, "application_version": application_version,
               "operation": operation, "deployment_lock": DEPLOY_LOCK,
               "target_query": schema_query(contract.read_text(encoding="utf-8"))}
    probe_callback = "send_upgrade_control_email" if operation == "email_probe" else "None"
    invocation = ("\ntry:\n    remote_main(" + repr(payload)
                  + ", recovery_validator=require_upgrade_recovery, "
                  "product_preflight=require_upgrade_product_configuration, "
                  f"smtp_probe={probe_callback})\n")
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
