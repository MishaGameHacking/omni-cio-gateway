from __future__ import annotations

from contextlib import suppress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts" / "rehearse_v10_wp14_jobs.py"
BACKUP_RUNNER = ROOT / "infrastructure" / "windows" / "run_wp10_backup.ps1"
BUNDLE_TOOL = ROOT / "scripts" / "v10_wp10_backup_bundle.py"
POSTGRES_WAIT_SECONDS = 45


class RehearsalError(RuntimeError):
    pass


def _tool(name: str) -> Path:
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    preferred = Path(program_files) / "PostgreSQL" / "18" / "bin" / f"{name}.exe"
    if preferred.is_file():
        return preferred
    resolved = shutil.which(f"{name}.exe") or shutil.which(name)
    if resolved is None:
        raise RehearsalError("POSTGRES_TOOL_NOT_FOUND")
    return Path(resolved)


def _run(
    args: list[str],
    *,
    env: dict[str, str] | None = None,
    capture: bool = False,
    reason: str,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RehearsalError(reason)
    return completed


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _probe_env(database: str, port: int) -> dict[str, str]:
    env = os.environ.copy()
    env["OMNI_CIO_WP14_DSN"] = (
        f"host=127.0.0.1 port={port} user=wp14_owner "
        f"dbname={database} connect_timeout=5"
    )
    prior_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(ROOT) if not prior_pythonpath else f"{ROOT}{os.pathsep}{prior_pythonpath}"
    )
    return env


def _probe(database: str, port: int, command: str) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(PROBE), command],
        cwd=ROOT,
        env=_probe_env(database, port),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    raw = completed.stdout.strip()
    if not raw:
        raise RehearsalError("WP14_PROBE_NO_OUTPUT")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RehearsalError("WP14_PROBE_INVALID_JSON") from exc
    if completed.returncode != 0 or parsed.get("status") != "PASS":
        reason = str(parsed.get("reason", "UNKNOWN")).upper()
        if re.fullmatch(r"[A-Z0-9_.-]+", reason) is None:
            reason = "UNKNOWN"
        raise RehearsalError(f"WP14_PROBE_FAILED:{reason}")
    return parsed


def _json_from_process(completed: subprocess.CompletedProcess[str], reason: str) -> Any:
    raw = completed.stdout.strip()
    if not raw:
        raise RehearsalError(f"{reason}:NO_OUTPUT")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RehearsalError(f"{reason}:INVALID_JSON") from exc


def main() -> int:
    started = time.monotonic()
    result: dict[str, Any] = {
        "schema_version": "1",
        "work_package": "WP14",
        "evidence_class": "LENOVO_SYNTHETIC_DURABLE_JOB_REHEARSAL",
        "status": "FAIL",
        "reason_code": "AUDIT_NOT_COMPLETED",
        "postgres_major": 18,
        "migration_count": 0,
        "migration_series_sha256": "",
        "job_state_digest_sha256": "",
        "duplicate_schedule_idempotent": False,
        "conflicting_replay_rejected": False,
        "concurrent_single_claim": False,
        "crash_retry_safe_recovered": False,
        "stale_worker_rejected": False,
        "retry_bound_enforced": False,
        "crash_reconcile_blocked": False,
        "validation_retry_blocked": False,
        "ambiguous_retry_blocked": False,
        "append_only_job_journal": False,
        "backup_integrity_pass": False,
        "corruption_rejected": False,
        "separate_restore_database_used": False,
        "restore_digest_exact_match": False,
        "temporary_state_cleaned": False,
        "real_secret_values_used": False,
        "private_portfolio_data_used": False,
        "broker_write_authority_used": False,
        "duration_ms": 0,
    }

    temp_root: Path | None = None
    pg_ctl: Path | None = None
    data_dir: Path | None = None
    try:
        initdb = _tool("initdb")
        pg_ctl = _tool("pg_ctl")
        createdb = _tool("createdb")
        pg_restore = _tool("pg_restore")
        pg_dump = _tool("pg_dump")
        psql = _tool("psql")

        version = _run(
            [str(psql), "--version"],
            capture=True,
            reason="POSTGRES_VERSION_FAILED",
        ).stdout
        if re.search(r"\b18\.\d+\b", version) is None:
            raise RehearsalError("POSTGRES_MAJOR_MISMATCH")

        base = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir()))
        temp_root = Path(tempfile.mkdtemp(prefix="wp14-audit-", dir=base))
        data_dir = temp_root / "pgdata"
        working_dir = temp_root / "working"
        bundle_dir = temp_root / "bundle"
        corrupt_dir = temp_root / "corrupt"
        server_log = temp_root / "postgres.log"
        working_dir.mkdir()
        bundle_dir.mkdir()
        corrupt_dir.mkdir()

        _run(
            [
                str(initdb),
                f"--pgdata={data_dir}",
                "--username=wp14_owner",
                "--auth=trust",
                "--encoding=UTF8",
                "--no-sync",
                "--no-instructions",
            ],
            reason="INITDB_FAILED",
        )
        port = _free_port()
        _run(
            [
                str(pg_ctl),
                "start",
                "-D",
                str(data_dir),
                "-l",
                str(server_log),
                "-w",
                "-t",
                str(POSTGRES_WAIT_SECONDS),
                "-o",
                f"-h 127.0.0.1 -p {port}",
            ],
            reason="POSTGRES_START_FAILED",
        )

        common = [
            "--host=127.0.0.1",
            f"--port={port}",
            "--username=wp14_owner",
            "--no-password",
        ]
        _run(
            [str(createdb), *common, "wp14_source"],
            reason="SOURCE_DB_CREATE_FAILED",
        )

        source = _probe("wp14_source", port, "exercise")
        for key in (
            "duplicate_schedule_idempotent",
            "conflicting_replay_rejected",
            "concurrent_single_claim",
            "crash_retry_safe_recovered",
            "stale_worker_rejected",
            "retry_bound_enforced",
            "crash_reconcile_blocked",
            "validation_retry_blocked",
            "ambiguous_retry_blocked",
            "append_only_job_journal",
        ):
            if source.get(key) is not True:
                raise RehearsalError("WP14_JOB_ASSERTION_FAILED")
            result[key] = True
        result["migration_count"] = int(source["migration_count"])
        result["migration_series_sha256"] = str(source["migration_series_sha256"])
        result["job_state_digest_sha256"] = str(source["job_state_digest_sha256"])

        backup = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(BACKUP_RUNNER),
                "-DatabaseName",
                "wp14_source",
                "-DatabaseUser",
                "wp14_owner",
                "-DatabaseHost",
                "127.0.0.1",
                "-DatabasePort",
                str(port),
                "-WorkingDirectory",
                str(working_dir),
                "-OutputDirectory",
                str(bundle_dir),
                "-BackupClass",
                "POSTGRES_LOGICAL_RECOVERY_REHEARSAL",
                "-PgDumpPath",
                str(pg_dump),
                "-PsqlPath",
                str(psql),
                "-PythonPath",
                sys.executable,
                "-AsJson",
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if backup.returncode != 0:
            raise RehearsalError("BACKUP_RUNNER_FAILED")
        backup_result = _json_from_process(backup, "BACKUP_RUNNER_OUTPUT")
        if backup_result.get("status") != "PASS":
            raise RehearsalError("BACKUP_RUNNER_DID_NOT_PASS")
        result["backup_integrity_pass"] = True

        archives = list(bundle_dir.glob("wp10-*.dump"))
        if len(archives) != 1:
            raise RehearsalError("BUNDLE_ARCHIVE_COUNT_INVALID")
        archive = archives[0]
        manifest = Path(f"{archive}.manifest.json")
        if not manifest.is_file():
            raise RehearsalError("BUNDLE_MANIFEST_MISSING")

        corrupt_archive = corrupt_dir / archive.name
        corrupt_manifest = Path(f"{corrupt_archive}.manifest.json")
        shutil.copy2(archive, corrupt_archive)
        shutil.copy2(manifest, corrupt_manifest)
        with corrupt_archive.open("ab") as handle:
            handle.write(b"tamper")
        corrupt_check = subprocess.run(
            [
                sys.executable,
                str(BUNDLE_TOOL),
                "verify",
                "--archive",
                str(corrupt_archive),
                "--manifest",
                str(corrupt_manifest),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if corrupt_check.returncode == 0:
            raise RehearsalError("CORRUPT_ARCHIVE_ACCEPTED")
        result["corruption_rejected"] = True

        _run(
            [str(createdb), *common, "wp14_restore"],
            reason="RESTORE_DB_CREATE_FAILED",
        )
        result["separate_restore_database_used"] = True
        _run(
            [
                str(pg_restore),
                *common,
                "--dbname=wp14_restore",
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
                str(archive),
            ],
            reason="PG_RESTORE_FAILED",
        )
        restored = _probe("wp14_restore", port, "digest")
        if (
            int(restored["migration_count"]) != int(source["migration_count"])
            or str(restored["migration_series_sha256"])
            != str(source["migration_series_sha256"])
            or str(restored["job_state_digest_sha256"])
            != str(source["job_state_digest_sha256"])
        ):
            raise RehearsalError("RESTORE_JOB_STATE_DIGEST_MISMATCH")
        result["restore_digest_exact_match"] = True
        result["status"] = "PASS"
        result["reason_code"] = "WP14_DURABLE_JOB_RECOVERY_PASS"
    except Exception as exc:
        reason = str(exc).upper()
        if re.fullmatch(r"[A-Z0-9_.:-]+", reason) is None:
            reason = type(exc).__name__.upper()
        result["reason_code"] = reason
    finally:
        if pg_ctl is not None and data_dir is not None and data_dir.is_dir():
            with suppress(Exception):
                subprocess.run(
                    [str(pg_ctl), "stop", "-D", str(data_dir), "-m", "fast", "-w"],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
        if temp_root is not None:
            with suppress(Exception):
                shutil.rmtree(temp_root)
        result["temporary_state_cleaned"] = (
            temp_root is None or not temp_root.exists()
        )
        result["duration_ms"] = int((time.monotonic() - started) * 1000)

    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())