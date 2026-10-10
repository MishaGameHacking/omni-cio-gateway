#!/usr/bin/env python3
"""Deploy the accepted OmniCIO auth application to the managed VDS."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import pathlib
import re
import runpy
import shlex
import ssl
import subprocess
import sys
import tarfile
import time
import tomllib
import urllib.error
import urllib.request
from collections.abc import Iterable
from email.message import Message

from inplace_upgrade import UpgradeBlocked, validate_operation
from timeweb_auth_postgres import (
    AmbiguousProviderError,
    EphemeralSsh,
    InfraError,
    TimewebApiError,
    TimewebClient,
    find_managed_server,
    find_vpc,
    integer_value,
    public_ipv4,
)
from timeweb_http import release_user_agent, release_version
from timeweb_recovery import REMOTE_STATUS_PATH

DOMAIN = "omnicio.ru"
SITE_MARKER = 'name="omni-cio-white-site"'
LEGAL_PAGES = {
    "/legal/privacy.html": "Политика обработки персональных данных",
    "/legal/consent.html": "Согласие на обработку персональных данных",
    "/legal/terms.html": "Пользовательские правила OMNICIO",
}
LEGAL_OPERATOR_MARKERS = (
    "__OMNICIO_OPERATOR_NAME__",
    "__OMNICIO_OPERATOR_EMAIL__",
)
LEGAL_DOCUMENT_KEYS = {
    "privacy": "privacy_policy",
    "consent": "personal_data_consent",
    "terms": "terms",
}
RUNTIME_ENV = "/etc/omnicio/runtime.env"
PRODUCT_ENV = "/etc/omnicio/product.env"
DEPLOY_LOCK = "/run/omnicio-auth-deploy.lock"
RELEASE_RE = re.compile(r"^[0-9a-f]{40}$")
INVALID_RELEASE_SHA = "Release SHA must be a full lowercase 40-character SHA"
BRAND_SOURCE = "assets/brand/omnicio-logo.png"
# The unchanged owner-provided PNG and the two existing backgrounds total 6 MiB.
# Keep a bounded archive budget that includes that explicit brand requirement.
MAX_RELEASE_ARCHIVE_BYTES = 8 * 1024 * 1024
BRAND_RUNTIME_FILES = (
    BRAND_SOURCE,
    "assets/brand/web/earth-hero.png",
    "assets/brand/web/auth-mountains.png",
)
BRAND_PUBLIC_MARK = "/assets/brand/omnicio-logo.png"
VERSION_PUBLIC_PATH = "/version.js"
JAVASCRIPT_CONTENT_TYPES = ("text/javascript", "application/javascript")
PNG_CONTENT_TYPE = "image/png"
# version.js holds only a bounded version/build object, never a runtime bundle.
MAX_RELEASE_METADATA_BYTES = 2048
PUBLIC_SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    ),
}
OPTIONAL_INTEGRATION_KEYS = (
    "AUTH_SMTP_HOST", "AUTH_SMTP_PORT", "AUTH_SMTP_USERNAME", "AUTH_SMTP_PASSWORD",
    "AUTH_SMTP_SENDER", "AUTH_SMTP_MODE", "MARKET_DATA_TOKEN",
    "ASSISTANT_BASE_URL", "ASSISTANT_API_KEY", "ASSISTANT_MODEL", "ASSISTANT_ENABLED",
    "ASSISTANT_ALLOWED_ENDPOINTS", "ASSISTANT_DAILY_REQUEST_LIMIT",
    "NOTIFICATIONS_ENABLED", "NOTIFICATION_EMAIL_ENABLED", "NOTIFICATION_CRYPTO_KEY",
    "NOTIFICATION_VAPID_PRIVATE_KEY",
    "NOTIFICATION_VAPID_SUBJECT", "NOTIFICATION_SMTP_HOST", "NOTIFICATION_SMTP_PORT",
    "NOTIFICATION_SMTP_USERNAME", "NOTIFICATION_SMTP_PASSWORD", "NOTIFICATION_SMTP_SENDER",
    "NOTIFICATION_SMTP_MODE", "OMNICIO_RESTORE_RECEIPT_KEY", "OMNICIO_RESTORE_ARCHIVE_KEY",
    "BILLING_ENABLED", "BILLING_TERMINAL_KEY", "BILLING_PASSWORD", "BILLING_AMOUNT_KOPECKS",
    "BILLING_PERIOD_DAYS", "BILLING_OFFER_VERSION", "BILLING_DESCRIPTION", "BILLING_TAXATION",
    "BILLING_TAX",
)
OPTIONAL_SECRET_KEYS = frozenset({
    "AUTH_SMTP_PASSWORD", "MARKET_DATA_TOKEN", "ASSISTANT_API_KEY", "NOTIFICATION_CRYPTO_KEY",
    "NOTIFICATION_VAPID_PRIVATE_KEY", "NOTIFICATION_SMTP_PASSWORD",
    "OMNICIO_RESTORE_RECEIPT_KEY", "OMNICIO_RESTORE_ARCHIVE_KEY", "BILLING_PASSWORD",
})


def add_summary(line: str) -> None:
    print(line)


def nginx_security_headers(indent: int) -> str:
    # Nginx discards inherited add_header directives whenever a location adds its own.
    # Render the same policy into every such scope and keep rollback configs self-contained.
    return "\n".join(
        f"{' ' * indent}add_header {name} "
        f"{json.dumps('$omnicio_referrer_policy' if name == 'Referrer-Policy' else value)} always;"
        for name, value in PUBLIC_SECURITY_HEADERS.items()
    )


def set_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def iter_release_files(root: pathlib.Path) -> Iterable[pathlib.Path]:
    paths = ("pyproject.toml", "requirements-runtime.txt", "src", "web", *BRAND_RUNTIME_FILES)
    for relative in paths:
        path = root / relative
        if path.is_file():
            yield path
            continue
        if not path.is_dir():
            continue
        for item in sorted(path.rglob("*")):
            if item.is_file() and "__pycache__" not in item.parts:
                yield item


def build_release_archive(root: pathlib.Path) -> str:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for source in iter_release_files(root):
            archive.add(source, arcname=source.relative_to(root), recursive=False)
    raw = buffer.getvalue()
    if not raw:
        raise InfraError("Release archive is empty")
    if len(raw) > MAX_RELEASE_ARCHIVE_BYTES:
        raise InfraError("Release archive unexpectedly exceeds 8 MiB")
    return base64.b64encode(raw).decode("ascii")


def runtime_is_ready(ssh: EphemeralSsh) -> bool:
    # Load the dependency-free contract from this exact reviewed checkout.
    contract = pathlib.Path(__file__).resolve().parents[2] / "src/omnicio/schema.py"
    query = runpy.run_path(str(contract))["READINESS_QUERY"]
    predicate = query.strip().removeprefix("SELECT").removesuffix("AS ready")
    schema_query = f"SELECT CASE WHEN {predicate} THEN 'ready' ELSE 'missing' END"
    command = (
        f"test -s {RUNTIME_ENV} && "
        f"grep -q '^DATABASE_URL=' {RUNTIME_ENV} && "
        f"grep -q '^CLIENT_IP_KEY=' {RUNTIME_ENV} && "
        f"grep -q '^BROKER_TOKEN_CRYPTO_KEY=' {RUNTIME_ENV} && "
        "command -v psql >/dev/null 2>&1 && "
        "set -a && "
        f". {RUNTIME_ENV} && "
        "set +a && "
        'test "$(PGCONNECT_TIMEOUT=10 psql "$DATABASE_URL" -X '
        '-v ON_ERROR_STOP=1 -Atqf - 2>/dev/null)" = "ready"'
    )
    try:
        # SQL is literal stdin: shell substitutions cannot alter its checks, and
        # the Windows SSH command line stays bounded as the schema grows.
        ssh.run(command, input_text=schema_query, timeout=45)
        return True
    except InfraError:
        return False


def _environment_value(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise InfraError("Runtime environment value contains a newline")
    escaped = (value.replace("\\", "\\\\").replace('"', '\\"')
               .replace("$", "\\$").replace("`", "\\`"))
    return f'"{escaped}"'


def _strict_boolean_environment(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise InfraError(f"{name} must be true or false")


def validate_product_environment() -> None:
    required_names = (
        "LEGAL_PRIVACY_VERSION",
        "LEGAL_CONSENT_VERSION",
        "LEGAL_TERMS_VERSION",
    )
    missing = [
        name
        for name in required_names
        if not os.environ.get(name, "").strip()
    ]
    if missing:
        raise InfraError(
            "Required auth product configuration is missing: "
            + ", ".join(missing)
        )

    operator_name = os.environ.get("LEGAL_OPERATOR_NAME", "").strip()
    operator_email = os.environ.get("LEGAL_OPERATOR_EMAIL", "").strip()
    if not 3 <= len(operator_name) <= 200:
        raise InfraError("LEGAL_OPERATOR_NAME must contain 3-200 characters")
    if not re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}", operator_email):
        raise InfraError("LEGAL_OPERATOR_EMAIL must be a valid email address")
    # Missing SMTP values may already be installed on the server. Verification
    # of the rendered auth config is the final deployment gate for registration.
    host = os.environ.get("AUTH_SMTP_HOST", "").strip()
    if host and not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host):
        raise InfraError("AUTH_SMTP_HOST must be a hostname")
    raw_port = os.environ.get("AUTH_SMTP_PORT", "465").strip() or "465"
    if not raw_port.isascii() or not raw_port.isdecimal() or not 1 <= int(raw_port) <= 65535:
        raise InfraError("AUTH_SMTP_PORT must be between 1 and 65535")
    mode = os.environ.get("AUTH_SMTP_MODE", "tls").strip() or "tls"
    if mode not in {"tls", "starttls"}:
        raise InfraError("AUTH_SMTP_MODE must use tls or starttls")
    _strict_boolean_environment("MARKET_DATA_DISTRIBUTION_APPROVED", False)


def verify_legal_document_version(body: str, path: str) -> None:
    name = f"LEGAL_{pathlib.PurePosixPath(path).stem.upper()}_VERSION"
    expected = os.environ.get(name, "").strip()
    versions = re.findall(r'<p class="legal-meta">OMNICIO · omnicio.ru · версия ([^<]+)</p>', body)
    if not expected or versions != [expected]:
        raise InfraError(f"Legal document version does not match deployment config: {path}")


def validate_legal_documents(repository_root: pathlib.Path) -> None:
    for public_path in LEGAL_PAGES:
        relative = "web" + public_path
        path = repository_root / relative
        try:
            body = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise InfraError(f"Legal document is unavailable: {relative}") from exc
        missing = [marker for marker in LEGAL_OPERATOR_MARKERS if marker not in body]
        if missing:
            raise InfraError(
                f"Legal document {relative} is missing operator placeholders"
            )
        verify_legal_document_version(body, public_path)


def build_product_environment(*, release_sha: str = "") -> str:
    if release_sha and not RELEASE_RE.fullmatch(release_sha):
        raise InfraError(INVALID_RELEASE_SHA)
    values = {
        "OMNICIO_RECOVERY_STATUS_PATH": REMOTE_STATUS_PATH,
        # Publication authority is always explicit and never inherited from a prior release.
        "MARKET_DATA_DISTRIBUTION_APPROVED": (
            "true" if _strict_boolean_environment("MARKET_DATA_DISTRIBUTION_APPROVED") else "false"
        ),
        # Authority must be explicitly revoked when the workflow variable is cleared.
        "OPERATOR_USER_ID": os.environ.get("OPERATOR_USER_ID", "").strip(),
        "LEGAL_OPERATOR_NAME": os.environ.get("LEGAL_OPERATOR_NAME", "").strip(),
        "LEGAL_OPERATOR_EMAIL": os.environ.get("LEGAL_OPERATOR_EMAIL", "").strip(),
        "LEGAL_PRIVACY_VERSION": os.environ.get("LEGAL_PRIVACY_VERSION", "").strip(),
        "LEGAL_CONSENT_VERSION": os.environ.get("LEGAL_CONSENT_VERSION", "").strip(),
        "LEGAL_TERMS_VERSION": os.environ.get("LEGAL_TERMS_VERSION", "").strip(),
        "SESSION_TTL_SECONDS": os.environ.get("SESSION_TTL_SECONDS", "34560000").strip(),
    }
    if release_sha:
        values["OMNICIO_RELEASE_BUILD"] = release_sha[:12]
    # Missing workflow secrets must not erase an integration configured on the server.
    values.update({
        name: os.environ[name] if name in OPTIONAL_SECRET_KEYS else os.environ[name].strip()
        for name in OPTIONAL_INTEGRATION_KEYS
        if os.environ.get(name, "").strip()
    })
    return "".join(
        f"{name}={_environment_value(value)}\n"
        for name, value in values.items()
    )


_PRODUCT_PREFLIGHT_PROGRAM = r'''
def _load_upgrade_product_settings(diagnostics: dict[str, object] | None = None) -> Settings:
    import pathlib

    observation = {} if diagnostics is None else diagnostics
    observation.update(dict.fromkeys((
        "auth_smtp_host_present", "auth_smtp_sender_present", "existing_receipt_key_present",
        "existing_archive_key_present", "market_data_token_present",
        "market_data_distribution_approved",
    )))
    environments = {}
    for name in ("runtime.env", "product.env"):
        observation["stage"] = ("runtime_environment" if name == "runtime.env"
                                else "product_environment")
        path = pathlib.Path("/etc/omnicio") / name
        try:
            text = _private_file(path, 65536)
        except FileNotFoundError:
            if name == "runtime.env":
                raise UpgradeBlocked("runtime_environment_missing") from None
            text = ""
        environments[name] = parse_environment(text)
    # Match the writer: explicit values replace base settings; only optional
    # integration keys absent from the new file survive from product.env.
    existing = environments["product.env"]
    observation.update({
        "stage": "environment_merge",
        "existing_receipt_key_present": bool(existing.get("OMNICIO_RESTORE_RECEIPT_KEY")),
        "existing_archive_key_present": bool(existing.get("OMNICIO_RESTORE_ARCHIVE_KEY")),
    })
    desired = parse_environment(__OMNICIO_PRODUCT_ENVIRONMENT__)
    for name in __OMNICIO_PRESERVED_KEYS__:
        if name in existing:
            desired.setdefault(name, existing[name])
    for name in ("OMNICIO_RESTORE_RECEIPT_KEY", "OMNICIO_RESTORE_ARCHIVE_KEY"):
        if existing.get(name) and desired.get(name) != existing[name]:
            raise UpgradeBlocked("recovery_key_rotation_requires_separate_procedure")
    effective = {**environments["runtime.env"], **desired}
    previous = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(effective)
        observation["stage"] = "settings_validation"
        settings = load_settings()
        observation.update({
            "stage": "auth_email_validation",
            "auth_smtp_host_present": bool(settings.auth_smtp_host),
            "auth_smtp_sender_present": bool(settings.auth_smtp_sender),
            "market_data_token_present": bool(settings.market_data_token),
            "market_data_distribution_approved": settings.market_data_distribution_approved,
        })
        validate_auth_email_configuration(settings)
        observation["stage"] = "push_validation"
        validate_push_configuration(
            settings.notification_vapid_private_key, settings.notification_vapid_subject,
        )
    finally:
        os.environ.clear()
        os.environ.update(previous)
    observation["stage"] = "email_readiness"
    if not settings.auth_email_ready:
        raise UpgradeBlocked("auth_email_configuration_required")
    observation["stage"] = "validated"
    return settings


def require_upgrade_product_configuration(
    diagnostics: dict[str, object] | None = None,
) -> dict[str, object]:
    try:
        settings = _load_upgrade_product_settings(diagnostics)
    except ConfigurationError:
        if diagnostics is None:
            raise
        raise UpgradeBlocked("product_configuration_invalid") from None
    return {
        "status": "configuration_ready",
        "smtp_delivery_verified": False,
        "market_token_configured": bool(settings.market_data_token),
        "market_distribution_approved": settings.market_data_distribution_approved,
    }
'''


_SMTP_PROBE_PROGRAM = r'''
def send_upgrade_control_email() -> dict[str, str]:
    settings = _load_upgrade_product_settings()
    recipient = normalize_login_email(__OMNICIO_SMTP_PROBE_RECIPIENT__)
    tag = __OMNICIO_SMTP_PROBE_TAG__
    domain = __OMNICIO_SMTP_PROBE_DOMAIN__
    # The accepted 1.3 runtime already provides this transport. Do not import
    # the candidate's AuthService or start a database-backed delivery worker.
    from omnicio.notifications import NotificationConfig, NotificationTransport

    transport = NotificationTransport(NotificationConfig(
        crypto_key=validate_auth_email_configuration(settings),
        public_origin="https://" + domain,
        email_enabled=True,
        smtp_host=settings.auth_smtp_host,
        smtp_port=settings.auth_smtp_port,
        smtp_username=settings.auth_smtp_username,
        smtp_password=settings.auth_smtp_password,
        smtp_sender=settings.auth_smtp_sender,
        smtp_mode=settings.auth_smtp_mode,
    ))
    result = transport.send_email({"email": recipient}, {
        "title": "OMNICIO — проверка доставки перед обновлением 1.4 [" + tag + "]",
        "body": (
            "Это контрольное письмо с рабочего сервера OMNICIO, отправленное "
            "по вашему разрешению перед обновлением 1.4. Действий с вашим "
            "аккаунтом не выполняется. Идентификатор проверки: " + tag
        ),
        "tag": tag,
    })
    # A queued or uncertain outcome is reported once, never retried here.
    # Provider acceptance does not claim receipt in the destination mailbox.
    return {
        "message_id": "<" + tag + "@" + domain + ">",
        "status": result.status,
        "code": result.code,
    }
'''


def _smtp_probe_parameters(release_sha: str) -> tuple[str, str]:
    if (not RELEASE_RE.fullmatch(release_sha)
            or os.environ.get("GITHUB_SHA") != release_sha
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"):
        raise InfraError("SMTP probe requires the first manual accepted-main attempt")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if re.fullmatch(r"[1-9]\d{0,19}", run_id, flags=re.ASCII) is None:
        raise InfraError("SMTP probe requires a valid workflow run ID")
    recipient = os.environ.get("OMNICIO_SMTP_PROBE_RECIPIENT", "")
    if not recipient.strip():
        raise InfraError("SMTP probe requires an explicitly selected recipient")
    return recipient, "smtp-probe-1.4-" + release_sha[:12] + "-" + run_id


def render_product_preflight(
    *, smtp_probe: bool = False, release_sha: str = "",
    capture_configuration_errors: bool = False,
) -> str:
    """Append the candidate's config reader to the reviewed upgrade program.

    Production secrets travel only over the existing SSH stdin. Normal checks
    neither change files nor send mail. The manual probe adds a separate callable
    for one explicitly authorized send; rendering never invokes it. The caller
    supplies UpgradeBlocked, _private_file and parse_environment.
    """
    from inplace_upgrade import render_source_definitions

    # Apply the same local checks as the app job before a database cutover can
    # start; runtime-only validation alone does not cover publication settings.
    probe = _smtp_probe_parameters(release_sha) if smtp_probe else None
    try:
        validate_product_environment()
        product_environment = build_product_environment(release_sha=release_sha)
    except (InfraError, ValueError):
        if not capture_configuration_errors:
            raise
        callbacks = ["require_upgrade_product_configuration"]
        if smtp_probe:
            callbacks.append("send_upgrade_control_email")
        unobserved = dict.fromkeys((
            "auth_smtp_host_present", "auth_smtp_sender_present", "existing_receipt_key_present",
            "existing_archive_key_present", "market_data_token_present",
            "market_data_distribution_approved",
        )) | {"stage": "candidate_validation"}
        return "\n".join(
            f'\ndef {name}(diagnostics: dict[str, object] | None = None) -> dict[str, object]:\n'
            '    if diagnostics is not None:\n'
            f'        diagnostics.update({unobserved!r})\n'
            '    raise UpgradeBlocked("product_configuration_invalid")\n'
            for name in callbacks
        )
    package = pathlib.Path(__file__).resolve().parents[2] / "src/omnicio"
    contract = package / "config.py"
    source = contract.read_text(encoding="utf-8").replace(
        "from __future__ import annotations\n", "", 1,
    )
    source += (
        "\nimport base64\nimport re\nfrom cryptography.fernet import Fernet, InvalidToken\n"
        "from cryptography.hazmat.primitives import serialization\n"
        "from cryptography.hazmat.primitives.asymmetric import ec\n"
    )
    source += render_source_definitions(package / "notifications.py", {
        "_EMAIL", "_MAILTO_SCHEME", "_HTTPS_SCHEME", "normalize_email", "_decode", "_b64",
        "push_public_key", "validate_push_configuration",
    })
    security_names = {"SecurityValueError", "encrypt_secret", "decrypt_secret"}
    service_names = {"validate_auth_email_configuration"}
    if smtp_probe:
        security_names.add("EMAIL_DOMAINS")
        service_names.add("normalize_login_email")
    source += render_source_definitions(package / "security.py", security_names)
    source += render_source_definitions(package / "service.py", service_names)
    source += "\n" + _PRODUCT_PREFLIGHT_PROGRAM.replace(
        "__OMNICIO_PRESERVED_KEYS__", repr(OPTIONAL_INTEGRATION_KEYS),
    ).replace(
        "__OMNICIO_PRODUCT_ENVIRONMENT__", repr(product_environment),
    )
    if probe is not None:
        recipient, tag = probe
        source += "\n" + _SMTP_PROBE_PROGRAM.replace(
            "__OMNICIO_SMTP_PROBE_TAG__", repr(tag),
        ).replace(
            "__OMNICIO_SMTP_PROBE_DOMAIN__", repr(DOMAIN),
        ).replace(
            "__OMNICIO_SMTP_PROBE_RECIPIENT__", repr(recipient),
        )
    return source


def preflight_product_environment(ssh: EphemeralSsh) -> None:
    """Reject missing future config before upload, environment writes or rollback."""
    source = pathlib.Path(__file__).with_name("inplace_upgrade.py").read_text(encoding="utf-8")
    program = source + "\n" + render_product_preflight() + r'''
try:
    print(json.dumps(require_upgrade_product_configuration(), sort_keys=True))
except Exception:
    # This boundary handles secret-bearing input: no traceback or values escape.
    print("OMNICIO_PREFLIGHT: product_configuration_not_ready", file=sys.stderr)
    raise SystemExit(1) from None
'''
    raw = ssh.run(
        f"flock -n {DEPLOY_LOCK} timeout --kill-after=5s 45s "
        "/opt/omnicio/current/.venv/bin/python -I -",
        input_text=program, timeout=60,
    )
    try:
        result = json.loads(raw) if len(raw) <= 2048 else None
    except ValueError:
        result = None
    if (not isinstance(result, dict) or set(result) != {
        "status", "smtp_delivery_verified", "market_token_configured",
        "market_distribution_approved",
    } or result.get("status") != "configuration_ready"
            or result.get("smtp_delivery_verified") is not False
            or type(result.get("market_token_configured")) is not bool
            or type(result.get("market_distribution_approved")) is not bool):
        raise InfraError("Effective product configuration was not confirmed")


def product_environment_backup_paths(release_sha: str) -> tuple[str, str]:
    if not RELEASE_RE.fullmatch(release_sha):
        raise InfraError(INVALID_RELEASE_SHA)
    return (
        f"{PRODUCT_ENV}.pre-{release_sha}",
        f"{PRODUCT_ENV}.pre-{release_sha}.state",
    )


def write_product_environment(ssh: EphemeralSsh, *, release_sha: str) -> None:
    backup, state = product_environment_backup_paths(release_sha)
    preserve_optional = "\n".join((
        "import pathlib, sys",
        "new, old = map(pathlib.Path, sys.argv[1:])",
        "text = new.read_text(encoding='utf-8')",
        "keys = {line.partition('=')[0] for line in text.splitlines()}",
        f"allowed = {OPTIONAL_INTEGRATION_KEYS!r}",
        "if old.exists():",
        "    for line in old.read_text(encoding='utf-8').splitlines():",
        "        key = line.partition('=')[0]",
        "        if key in allowed and key not in keys:",
        "            text += line + '\\n'",
        "            keys.add(key)",
        "new.write_text(text, encoding='utf-8')",
    ))
    command = (
        "set -euo pipefail; umask 077; "
        f"tmp={PRODUCT_ENV}.tmp-{release_sha}; "
        f"if [ -f {PRODUCT_ENV} ]; then "
        f"cp -p {PRODUCT_ENV} {backup}; printf 'present\\n' > {state}; "
        f"else rm -f {backup}; printf 'absent\\n' > {state}; fi; "
        'cat > "$tmp"; '
        f'python3 -c {shlex.quote(preserve_optional)} "$tmp" {PRODUCT_ENV}; '
        'chmod 600 "$tmp"; '
        f"mv -f \"$tmp\" {PRODUCT_ENV}"
    )
    ssh.run(command, input_text=build_product_environment(release_sha=release_sha))


def commit_product_environment(ssh: EphemeralSsh, *, release_sha: str) -> None:
    backup, state = product_environment_backup_paths(release_sha)
    try:
        ssh.run(f"rm -f {backup} {state}")
    except InfraError:
        # Backup cleanup is housekeeping after a proven healthy release. It must
        # never turn a proven healthy release into a failed deployment.
        add_summary("- Warning: stale product environment rollback backup remains.")


def release_rollback_contract() -> str:
    """Read the compatibility contract from this exact reviewed checkout."""
    project = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"
    with project.open("rb") as handle:
        contract = tomllib.load(handle)["tool"]["omnicio"]["runtime"]["rollback_contract"]
    if not isinstance(contract, str) or re.fullmatch(r"[a-z][a-z0-9-]{0,63}", contract) is None:
        raise ValueError("The reviewed runtime rollback contract is invalid")
    return contract


# Do not import either release's Python modules or ask the old application to
# certify itself. Only root-owned static metadata under the release tree may
# declare compatibility with the contract accepted in this reviewed checkout.
_ROLLBACK_COMPATIBILITY_PROGRAM = r"""import os
import pathlib
import re
import stat
import sys
import tomllib

EXPECTED_CONTRACT = __OMNICIO_ROLLBACK_CONTRACT__
MAX_METADATA_BYTES = 65536


def trusted_metadata(info: os.stat_result, *, directory: bool) -> bool:
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    return info.st_uid == 0 and not info.st_mode & 0o022 and expected_type(info.st_mode)


def read_contract(release: pathlib.Path, releases_root: pathlib.Path) -> str:
    if (release.parent != releases_root or not release.is_absolute()
            or re.fullmatch(r"[0-9a-f]{40}", release.name) is None
            or release.resolve(strict=True) != release):
        raise ValueError("untrusted_release_path")
    for directory in (release, *release.parents):
        if not trusted_metadata(directory.lstat(), directory=True):
            raise ValueError("untrusted_release_directory")
    metadata = release / "pyproject.toml"
    info = metadata.lstat()
    if (not trusted_metadata(info, directory=False)
            or not 0 < info.st_size <= MAX_METADATA_BYTES):
        raise ValueError("untrusted_release_metadata")
    with metadata.open("rb") as handle:
        body = handle.read(MAX_METADATA_BYTES + 1)
    if len(body) > MAX_METADATA_BYTES:
        raise ValueError("release_metadata_too_large")
    project = tomllib.loads(body.decode("utf-8"))
    if project["project"]["name"] != "omnicio-gateway":
        raise ValueError("unexpected_release_project")
    contract = project["tool"]["omnicio"]["runtime"]["rollback_contract"]
    if not isinstance(contract, str):
        raise ValueError("invalid_release_contract")
    return contract


def compatible(
    candidate: str | pathlib.Path, previous: str | pathlib.Path,
    releases_root: pathlib.Path = pathlib.Path("/opt/omnicio/releases"),
) -> bool:
    try:
        return (read_contract(pathlib.Path(candidate), releases_root) == EXPECTED_CONTRACT
                and read_contract(pathlib.Path(previous), releases_root) == EXPECTED_CONTRACT)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, RuntimeError):
        return False


if __name__ == "__main__":
    sys.exit(0 if len(sys.argv) == 3 and compatible(sys.argv[1], sys.argv[2]) else 45)
""".replace("__OMNICIO_ROLLBACK_CONTRACT__", json.dumps(release_rollback_contract()))

_ROLLBACK_COMPATIBILITY_GUARD = r"""require_compatible_rollback() {
    if ! python3 -I - "$RELEASE" "${PREVIOUS_APP:-}" <<'OMNICIO_ROLLBACK_PY'
__OMNICIO_ROLLBACK_PROGRAM__
OMNICIO_ROLLBACK_PY
    then
        # Stop the candidate too: neither unavailable service nor an unknown
        # old runtime may continue writing after compatibility becomes unknown.
        STOP_CONFIRMED=1
        systemctl stop omnicio-auth.service omnicio-observer.timer omnicio-observer.service \
            || STOP_CONFIRMED=0
        systemctl disable omnicio-auth.service omnicio-observer.timer omnicio-observer.service \
            || STOP_CONFIRMED=0
        if [ "$STOP_CONFIRMED" != "1" ]; then
            printf '%s\n' 'rollback_blocked_shutdown_unconfirmed' \
                > "/run/omnicio-auth-deploy-$SHA.rollback-blocked"
            printf '%s\n' 'Rollback blocked; service shutdown was not confirmed.' >&2
            exit 46
        fi
        printf '%s\n' 'rollback_blocked_incompatible_runtime_contract' \
            > "/run/omnicio-auth-deploy-$SHA.rollback-blocked"
        printf '%s\n' 'Rollback blocked: incompatible or unknown runtime contract.' \
            'Services stopped; candidate and environment retained.' >&2
        exit 45
    fi
}
""".replace("__OMNICIO_ROLLBACK_PROGRAM__", _ROLLBACK_COMPATIBILITY_PROGRAM)


_REMOTE_DEPLOY_TEMPLATE = r"""set -euo pipefail

SHA="$1"
RELEASE="/opt/omnicio/releases/$SHA"
APP_CURRENT="/opt/omnicio/current"
WEB_BASE="/var/www/omnicio.ru"
WEB_RELEASE="$WEB_BASE/releases/$SHA"
WEB_CURRENT="$WEB_BASE/current"
SERVICE="/etc/systemd/system/omnicio-auth.service"
OBSERVER_SERVICE="/etc/systemd/system/omnicio-observer.service"
OBSERVER_TIMER="/etc/systemd/system/omnicio-observer.timer"
NGINX_SITE="/etc/nginx/sites-available/omnicio.ru"
STATE="/run/omnicio-auth-deploy-$SHA.state"

__OMNICIO_ROLLBACK_GUARD__

test -s /etc/omnicio/runtime.env
test -s /etc/letsencrypt/live/omnicio.ru/fullchain.pem
test -s /etc/letsencrypt/live/omnicio.ru/privkey.pem
test -s "$RELEASE/pyproject.toml"
test -s "$RELEASE/web/index.html"

PREVIOUS_APP="$(readlink -f "$APP_CURRENT" 2>/dev/null || true)"
PREVIOUS_WEB="$(readlink -f "$WEB_CURRENT" 2>/dev/null || true)"
OBSERVER_TIMER_WAS_ENABLED=0
OBSERVER_TIMER_WAS_ACTIVE=0
if systemctl is-enabled omnicio-observer.timer >/dev/null 2>&1; then
    OBSERVER_TIMER_WAS_ENABLED=1
fi
if systemctl is-active omnicio-observer.timer >/dev/null 2>&1; then
    OBSERVER_TIMER_WAS_ACTIVE=1
fi
{
    printf 'PREVIOUS_APP=%q\n' "$PREVIOUS_APP"
    printf 'PREVIOUS_WEB=%q\n' "$PREVIOUS_WEB"
    printf 'OBSERVER_TIMER_WAS_ENABLED=%q\n' "$OBSERVER_TIMER_WAS_ENABLED"
    printf 'OBSERVER_TIMER_WAS_ACTIVE=%q\n' "$OBSERVER_TIMER_WAS_ACTIVE"
} > "$STATE"
chmod 600 "$STATE"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv ca-certificates nginx curl openssl

install_tbank_trusted_ca() {
    CERT_TMP="$(mktemp -d)"
    ROOT_CER="$CERT_TMP/russian_trusted_root_ca.cer"
    SUB_CER="$CERT_TMP/russian_trusted_sub_ca.cer"
    ROOT_PEM="$CERT_TMP/russian_trusted_root_ca.pem"
    SUB_PEM="$CERT_TMP/russian_trusted_sub_ca.pem"

    curl --fail --location --silent --show-error --retry 3 \
        --connect-timeout 10 --max-time 30 \
        -o "$ROOT_CER" \
        "https://gu-st.ru/content/Other/doc/russian_trusted_root_ca.cer"
    curl --fail --location --silent --show-error --retry 3 \
        --connect-timeout 10 --max-time 30 \
        -o "$SUB_CER" \
        "https://gu-st.ru/content/Other/doc/russian_trusted_sub_ca.cer"

    if openssl x509 -in "$ROOT_CER" -noout >/dev/null 2>&1; then
        cp "$ROOT_CER" "$ROOT_PEM"
    else
        openssl x509 -inform DER -in "$ROOT_CER" -out "$ROOT_PEM"
    fi
    if openssl x509 -in "$SUB_CER" -noout >/dev/null 2>&1; then
        cp "$SUB_CER" "$SUB_PEM"
    else
        openssl x509 -inform DER -in "$SUB_CER" -out "$SUB_PEM"
    fi

    openssl x509 -in "$ROOT_PEM" -noout -subject | grep -F "Russian Trusted Root CA" >/dev/null
    openssl x509 -in "$SUB_PEM" -noout -subject | grep -F "Russian Trusted Sub CA" >/dev/null
    openssl verify -CAfile "$ROOT_PEM" "$SUB_PEM" >/dev/null

    install -m 0644 "$ROOT_PEM" /usr/local/share/ca-certificates/russian_trusted_root_ca.crt
    install -m 0644 "$SUB_PEM" /usr/local/share/ca-certificates/russian_trusted_sub_ca.crt
    update-ca-certificates >/dev/null
    rm -rf "$CERT_TMP"
}

install_tbank_trusted_ca

if curl --silent --show-error --connect-timeout 5 --max-time 10 \
    -o /dev/null "https://invest-public-api.tbank.ru/"; then
    echo "T-Invest TLS probe: ok"
else
    echo "T-Invest TLS probe: failed" >&2
fi

if ! id omnicio >/dev/null 2>&1; then
    useradd --system --home /nonexistent --shell /usr/sbin/nologin omnicio
fi

python3 -m venv "$RELEASE/.venv"
"$RELEASE/.venv/bin/python" -m pip install --disable-pip-version-check -q \
    --only-binary=:all: --require-hashes -r "$RELEASE/requirements-runtime.txt"
"$RELEASE/.venv/bin/python" -m pip install --disable-pip-version-check -q \
    --no-deps --no-build-isolation --no-index --only-binary=:all: "$RELEASE"

# Keep the signing identity outside product.env rollback and release cleanup.
# The helper preserves an existing key, writes private files atomically, and
# exposes only a readiness status. Auth SMTP is configured separately.
"$RELEASE/.venv/bin/python" -m omnicio.notification_setup

install -d -m 0755 "$WEB_RELEASE/assets" "$WEB_RELEASE/assets/brand" "$WEB_RELEASE/legal"
install -m 0644 "$RELEASE/assets/brand/omnicio-logo.png" \
    "$WEB_RELEASE/assets/brand/omnicio-logo.png"
install -m 0644 "$RELEASE/assets/brand/web/earth-hero.png" \
    "$WEB_RELEASE/assets/brand/earth-hero.png"
install -m 0644 "$RELEASE/assets/brand/web/auth-mountains.png" \
    "$WEB_RELEASE/assets/brand/auth-mountains.png"
set -a
. /etc/omnicio/product.env
set +a

python3 - "$RELEASE/web/legal" "$WEB_RELEASE/legal" "$SHA" <<'PY'
import html
import os
import pathlib
import sys

source = pathlib.Path(sys.argv[1])
destination = pathlib.Path(sys.argv[2])
replacements = {
    "__OMNICIO_OPERATOR_NAME__": html.escape(os.environ["LEGAL_OPERATOR_NAME"], quote=True),
    "__OMNICIO_OPERATOR_EMAIL__": html.escape(os.environ["LEGAL_OPERATOR_EMAIL"], quote=True),
    "__OMNICIO_BUILD__": sys.argv[3][:12],
}
for name in ("privacy.html", "consent.html", "terms.html"):
    body = (source / name).read_text(encoding="utf-8")
    for marker, value in replacements.items():
        body = body.replace(marker, value)
    if "__OMNICIO_OPERATOR_" in body or "__OMNICIO_BUILD__" in body:
        raise SystemExit(f"unresolved legal publication marker: {name}")
    (destination / name).write_text(body, encoding="utf-8")
PY
chmod 0644 "$WEB_RELEASE/legal/privacy.html" \
    "$WEB_RELEASE/legal/consent.html" "$WEB_RELEASE/legal/terms.html"

# The installed package and browser CI share this exact renderer. It resolves
# the version, build, theme and offline assets before the release is promoted.
"$RELEASE/.venv/bin/python" -m omnicio.web_assets "$RELEASE/web" "$WEB_RELEASE" "$SHA"

cat > "$SERVICE.new" <<'EOF'
[Unit]
Description=OmniCIO authentication API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=omnicio
Group=omnicio
WorkingDirectory=/opt/omnicio/current
EnvironmentFile=/etc/omnicio/runtime.env
EnvironmentFile=/etc/omnicio/product.env
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ExecStart=/opt/omnicio/current/.venv/bin/uvicorn omnicio.main:app \
    --host 127.0.0.1 --port 8001 --workers 1 --limit-concurrency 64 \
    --backlog 128 --timeout-keep-alive 5 --timeout-graceful-shutdown 30 \
    --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=on-failure
RestartSec=3
TimeoutStartSec=45
# Allow HTTP drain plus worker cleanup; hung I/O still reaches the hard deadline.
TimeoutStopSec=90
KillMode=control-group
SendSIGKILL=yes
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
CapabilityBoundingSet=

[Install]
WantedBy=multi-user.target
EOF
mv "$SERVICE.new" "$SERVICE"
chmod 0644 "$SERVICE"

cat > "$OBSERVER_SERVICE.new" <<'EOF'
[Unit]
Description=OmniCIO daily portfolio observer
After=network-online.target omnicio-auth.service
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=simple
User=omnicio
Group=omnicio
WorkingDirectory=/opt/omnicio/current
EnvironmentFile=/etc/omnicio/runtime.env
EnvironmentFile=/etc/omnicio/product.env
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ExecStart=/opt/omnicio/current/.venv/bin/python -m omnicio.observer
Restart=on-failure
RestartSec=180
TimeoutStartSec=1200
RuntimeMaxSec=1500
TimeoutStopSec=30
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
CapabilityBoundingSet=

[Install]
WantedBy=multi-user.target
EOF
mv "$OBSERVER_SERVICE.new" "$OBSERVER_SERVICE"
chmod 0644 "$OBSERVER_SERVICE"

cat > "$OBSERVER_TIMER.new" <<'EOF'
[Unit]
Description=Run OmniCIO portfolio observer daily in Moscow time

[Timer]
OnCalendar=*-*-* 06:15:00 Europe/Moscow
OnBootSec=2min
OnUnitInactiveSec=5min
Persistent=true
AccuracySec=1min
Unit=omnicio-observer.service

[Install]
WantedBy=timers.target
EOF
mv "$OBSERVER_TIMER.new" "$OBSERVER_TIMER"
chmod 0644 "$OBSERVER_TIMER"

systemctl daemon-reload
# Drain the old read-only worker before activating a new connection lifecycle.
# An interrupted running job is recovered through its existing durable job state.
systemctl stop omnicio-observer.timer omnicio-observer.service
ln -sfn "$RELEASE" "$APP_CURRENT"
systemctl enable omnicio-auth.service >/dev/null
systemctl restart omnicio-auth.service

READY=0
for _ in $(seq 1 20); do
    if curl -fsS --max-time 3 http://127.0.0.1:8001/health/ready >/dev/null; then
        READY=1
        break
    fi
    sleep 2
done

if [ "$READY" != "1" ]; then
    require_compatible_rollback
    if [ -n "$PREVIOUS_APP" ] && [ -d "$PREVIOUS_APP" ]; then
        ln -sfn "$PREVIOUS_APP" "$APP_CURRENT"
        systemctl restart omnicio-auth.service || true
    fi
    exit 41
fi

if [ -f "$NGINX_SITE" ]; then
    cp -a "$NGINX_SITE" "$NGINX_SITE.pre-auth"
fi

cat > "$NGINX_SITE.new" <<'EOF'
limit_req_zone $binary_remote_addr zone=omnicio_auth_start:10m rate=10r/m;
limit_req_zone $binary_remote_addr zone=omnicio_api:10m rate=120r/m;
limit_conn_zone $binary_remote_addr zone=omnicio_conn:10m;

map $upstream_http_referrer_policy $omnicio_referrer_policy {
    default __OMNICIO_DEFAULT_REFERRER_POLICY__;
    "no-referrer" "no-referrer";
}

server {
    listen 80;
    listen [::]:80;
    server_name omnicio.ru;

    server_tokens off;
    client_max_body_size 16k;
    client_body_timeout 10s;
    client_header_timeout 10s;
    keepalive_timeout 15s;
    send_timeout 30s;
    limit_conn omnicio_conn 32;
    limit_conn_status 429;

    location /.well-known/acme-challenge/ {
        root /var/www/omnicio.ru/releases/__OMNICIO_PUBLIC_RELEASE__;
        try_files $uri =404;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name omnicio.ru;

    server_tokens off;
    client_max_body_size 16k;
    client_body_timeout 10s;
    client_header_timeout 10s;
    keepalive_timeout 15s;
    send_timeout 30s;
    limit_conn omnicio_conn 32;
    limit_conn_status 429;

    ssl_certificate /etc/letsencrypt/live/omnicio.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/omnicio.ru/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Root and build header are pinned together, including during graceful reload.
    root /var/www/omnicio.ru/releases/__OMNICIO_PUBLIC_RELEASE__;
    index index.html;

    proxy_hide_header Referrer-Policy;
__OMNICIO_SERVER_SECURITY_HEADERS__

    location ^~ /api/auth/email/ {
        client_max_body_size 4k;
        limit_req zone=omnicio_auth_start burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
        proxy_send_timeout 30s;
    }

    location = /api/assistant/messages {
        client_max_body_size 128k;
        limit_req zone=omnicio_auth_start burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
        proxy_send_timeout 30s;
    }

    location = /api/preferences {
        client_max_body_size 64k;
        limit_req zone=omnicio_api burst=60 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
        proxy_send_timeout 30s;
    }

    location = /api/profile/strategy/research {
        client_max_body_size 16k;
        limit_req zone=omnicio_auth_start burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 300s;
        proxy_send_timeout 30s;
    }

    location = /api/research/evidence {
        client_max_body_size 17m;
        limit_req zone=omnicio_auth_start burst=5 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
        proxy_send_timeout 30s;
    }

    location ~ ^/api/market/instruments/[^/]+$ {
        client_max_body_size 16k;
        limit_req zone=omnicio_api burst=60 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 120s;
        proxy_send_timeout 30s;
    }

    location /api/ {
        limit_req zone=omnicio_api burst=60 nodelay;
        limit_req_status 429;
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 30s;
        proxy_send_timeout 30s;
    }

    location /health/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 10s;
    }

    location = /assets/tokens.css {
        try_files $uri =404;
__OMNICIO_LOCATION_SECURITY_HEADERS__
        add_header Cache-Control "no-cache";
    }

    location = /assets/config.js {
        try_files $uri =404;
__OMNICIO_LOCATION_SECURITY_HEADERS__
        add_header Cache-Control "no-cache";
    }

    location = /assets/app.css {
        try_files $uri =404;
__OMNICIO_LOCATION_SECURITY_HEADERS__
        add_header Cache-Control "no-cache";
    }

    location = /assets/app.js {
        try_files $uri =404;
__OMNICIO_LOCATION_SECURITY_HEADERS__
        add_header Cache-Control "no-cache";
    }

    location = /assets/workspace.js {
        try_files $uri =404;
__OMNICIO_LOCATION_SECURITY_HEADERS__
        add_header Cache-Control "no-cache";
    }

    location = /assets/i18n.js {
        try_files $uri =404;
__OMNICIO_LOCATION_SECURITY_HEADERS__
        add_header Cache-Control "no-cache";
    }

    location /assets/ {
        try_files $uri =404;
__OMNICIO_LOCATION_SECURITY_HEADERS__
        add_header Cache-Control "public, max-age=86400";
    }

    location = /version.js {
        try_files $uri =404;
__OMNICIO_LOCATION_SECURITY_HEADERS__
        add_header Cache-Control "no-cache";
    }

    location / {
        try_files $uri $uri/ /index.html;
__OMNICIO_LOCATION_SECURITY_HEADERS__
        add_header Cache-Control "no-cache";
    }
}
EOF

mv "$NGINX_SITE.new" "$NGINX_SITE"
ln -sfn "$NGINX_SITE" /etc/nginx/sites-enabled/omnicio.ru
rm -f /etc/nginx/sites-enabled/default
ln -sfn "$WEB_RELEASE" "$WEB_CURRENT"

if ! nginx -t; then
    require_compatible_rollback
    if [ -f "$NGINX_SITE.pre-auth" ]; then
        mv "$NGINX_SITE.pre-auth" "$NGINX_SITE"
    fi
    if [ -n "$PREVIOUS_WEB" ] && [ -d "$PREVIOUS_WEB" ]; then
        ln -sfn "$PREVIOUS_WEB" "$WEB_CURRENT"
    fi
    nginx -t || true
    exit 42
fi

systemctl reload nginx
systemctl enable omnicio-observer.timer >/dev/null
systemctl restart omnicio-observer.timer
systemctl is-enabled omnicio-observer.timer >/dev/null
systemctl is-active omnicio-observer.timer >/dev/null
"""
REMOTE_DEPLOY_SCRIPT = _REMOTE_DEPLOY_TEMPLATE.replace(
    "__OMNICIO_ROLLBACK_GUARD__", _ROLLBACK_COMPATIBILITY_GUARD,
).replace(
    "__OMNICIO_SERVER_SECURITY_HEADERS__", nginx_security_headers(4),
).replace(
    "__OMNICIO_LOCATION_SECURITY_HEADERS__", nginx_security_headers(8)
    + '\n        add_header X-Omnicio-Build "__OMNICIO_PUBLIC_BUILD__";',
).replace(
    "__OMNICIO_DEFAULT_REFERRER_POLICY__", json.dumps(PUBLIC_SECURITY_HEADERS["Referrer-Policy"]),
)


REMOTE_ROLLBACK_SCRIPT = r"""set -euo pipefail

SHA="$1"
RELEASE="/opt/omnicio/releases/$SHA"
STATE="/run/omnicio-auth-deploy-$SHA.state"
NGINX_SITE="/etc/nginx/sites-available/omnicio.ru"
PRODUCT_ENV="/etc/omnicio/product.env"
PRODUCT_ENV_BACKUP="$PRODUCT_ENV.pre-$SHA"
PRODUCT_ENV_STATE="$PRODUCT_ENV.pre-$SHA.state"

__OMNICIO_ROLLBACK_GUARD__

if [ -s "$STATE" ]; then
    . "$STATE"
elif [ ! -e "$STATE" ]; then
    # product.env can fail before deploy_remote creates its state. Only the
    # still-active, distinct, independently compatible release is safe here.
    PREVIOUS_APP="$(readlink -f /opt/omnicio/current 2>/dev/null || true)"
    if [ "$PREVIOUS_APP" = "$RELEASE" ]; then
        PREVIOUS_APP=""
    fi
fi
# Check before restoring even product.env: it may re-enable retired readers.
# Missing or untrusted state is not evidence that the old runtime is safe.
require_compatible_rollback

if [ -f "$PRODUCT_ENV_STATE" ]; then
    PRODUCT_ENV_PREVIOUS="$(cat "$PRODUCT_ENV_STATE")"
    if [ "$PRODUCT_ENV_PREVIOUS" = "present" ]; then
        test -f "$PRODUCT_ENV_BACKUP"
        cp -p "$PRODUCT_ENV_BACKUP" "$PRODUCT_ENV"
    elif [ "$PRODUCT_ENV_PREVIOUS" = "absent" ]; then
        rm -f "$PRODUCT_ENV"
    else
        exit 44
    fi
fi

# An environment-only failure never began an app/web/timer switch. Do not
# restore an unrelated nginx backup or restart the unchanged compatible app.
if [ ! -s "$STATE" ]; then
    exit 0
fi

RESTORE_CONFIRMED=1
if [ -s "$STATE" ]; then
    if [ -n "$PREVIOUS_APP" ] && [ -d "$PREVIOUS_APP" ]; then
        ln -sfn "$PREVIOUS_APP" /opt/omnicio/current
        systemctl restart omnicio-auth.service || RESTORE_CONFIRMED=0
    fi
    if [ -n "$PREVIOUS_WEB" ] && [ -d "$PREVIOUS_WEB" ]; then
        ln -sfn "$PREVIOUS_WEB" /var/www/omnicio.ru/current
    fi

    if [ "${OBSERVER_TIMER_WAS_ENABLED:-0}" = "1" ]; then
        systemctl enable omnicio-observer.timer >/dev/null 2>&1 || RESTORE_CONFIRMED=0
    else
        systemctl disable omnicio-observer.timer >/dev/null 2>&1 || RESTORE_CONFIRMED=0
    fi
    if [ "${OBSERVER_TIMER_WAS_ACTIVE:-0}" = "1" ]; then
        systemctl restart omnicio-observer.timer >/dev/null 2>&1 || RESTORE_CONFIRMED=0
    else
        systemctl stop omnicio-observer.timer >/dev/null 2>&1 || RESTORE_CONFIRMED=0
    fi
fi

if [ -f "$NGINX_SITE.pre-auth" ]; then
    mv "$NGINX_SITE.pre-auth" "$NGINX_SITE"
fi
nginx -t && systemctl reload nginx || RESTORE_CONFIRMED=0
if [ "$RESTORE_CONFIRMED" != "1" ]; then
    exit 47
fi
""".replace("__OMNICIO_ROLLBACK_GUARD__", _ROLLBACK_COMPATIBILITY_GUARD)


def upload_release(
    ssh: EphemeralSsh,
    *,
    archive_b64: str,
    release_sha: str,
) -> None:
    if not RELEASE_RE.fullmatch(release_sha):
        raise InfraError(INVALID_RELEASE_SHA)
    release = f"/opt/omnicio/releases/{release_sha}"
    current = ssh.run("readlink -f /opt/omnicio/current 2>/dev/null || true").strip()
    if current == release:
        # A retry must never erase the venv/source used by live worker processes
        # or turn the rollback target into the partially uploaded candidate.
        raise InfraError("The requested release is already active; no files were changed")
    command = (
        "set -euo pipefail; "
        # Recheck remotely immediately before removal as a second safety boundary.
        f'test "$(readlink -f /opt/omnicio/current 2>/dev/null || true)" != {release}; '
        f"rm -rf {release}; "
        f"install -d -m 0755 {release}; "
        f"base64 -d | tar --no-same-owner --no-same-permissions -xzf - -C {release}; "
        f"chmod 0644 {release}/pyproject.toml; "
        # A retry of the same SHA must not consume a previous attempt's rollback
        # target if product.env fails before deploy_remote records new state.
        f"rm -f /run/omnicio-auth-deploy-{release_sha}.state "
        f"/run/omnicio-auth-deploy-{release_sha}.rollback-blocked"
    )
    ssh.run(
        f"flock -w 855 {DEPLOY_LOCK} timeout --kill-after=5s 60s "
        f"bash -c {shlex.quote(command)}",
        input_text=archive_b64, timeout=960,
    )


def deploy_remote(ssh: EphemeralSsh, *, release_sha: str) -> None:
    if not RELEASE_RE.fullmatch(release_sha):
        raise InfraError(INVALID_RELEASE_SHA)
    # Keep the remote process group bounded before the SSH controller deadline.
    # The same lock makes rollback wait after an ambiguous SSH disconnection.
    ssh.run(
        f"flock -n {DEPLOY_LOCK} timeout --kill-after=15s 840s bash -s -- {release_sha}",
        input_text=REMOTE_DEPLOY_SCRIPT.replace(
            "__OMNICIO_PUBLIC_BUILD__", release_sha[:12],
        ).replace("__OMNICIO_PUBLIC_RELEASE__", release_sha),
        timeout=900,
    )


def rollback_remote(ssh: EphemeralSsh, *, release_sha: str) -> None:
    if not RELEASE_RE.fullmatch(release_sha):
        raise InfraError(INVALID_RELEASE_SHA)
    try:
        ssh.run(
            f"flock -w 855 {DEPLOY_LOCK} timeout --kill-after=5s 180s bash -s -- {release_sha}",
            input_text=REMOTE_ROLLBACK_SCRIPT, timeout=1080,
        )
    except InfraError as exc:
        if "exit_code=45)" in str(exc):
            add_summary(
                "- Rollback blocked: incompatible or unknown runtime contract. "
                "Auth and observer were stopped; candidate and environment retained. "
                "An accepted recovery decision is required before restarting services."
            )
        elif "exit_code=46)" in str(exc):
            add_summary(
                "- Rollback blocked: service shutdown could not be confirmed. "
                "Candidate and environment retained; inspect auth and observer state immediately."
            )
        else:
            add_summary("- Warning: application rollback was not confirmed; inspect release state.")


def verify_public_security_headers(
    headers: Message, path: str, *, referrer_policy: str | None = None,
) -> None:
    expected_headers = dict(PUBLIC_SECURITY_HEADERS)
    if referrer_policy is not None:
        expected_headers["Referrer-Policy"] = referrer_policy
    for name, expected in expected_headers.items():
        if headers.get_all(name, []) != [expected]:
            raise InfraError(f"Public application security header invalid: {name}: {path}")


def fetch_public(
    path: str, context: ssl.SSLContext, *, expected_build: str = "",
) -> tuple[bytes, str]:
    request = urllib.request.Request(
        f"https://{DOMAIN}{path}",
        headers={"User-Agent": release_user_agent("omnicio-auth-deploy")},
    )
    with urllib.request.urlopen(request, timeout=15, context=context) as response:
        if response.status != 200:
            raise InfraError(f"Public application returned non-200: {path}")
        verify_public_security_headers(response.headers, path)
        if expected_build and response.headers.get_all("X-Omnicio-Build", []) != [expected_build]:
            raise InfraError(f"Public application build header does not match release: {path}")
        body = response.read(4 * 1024 * 1024 + 1)
        if len(body) > 4 * 1024 * 1024:
            raise InfraError(f"Public application response is too large: {path}")
        return body, response.headers.get_content_type()


def verify_public_root(body: bytes, release_sha: str) -> None:
    root_body = body.decode(errors="replace")
    required = {
        SITE_MARKER: "Public auth page verification failed",
        BRAND_PUBLIC_MARK: "Public auth page does not use approved brand mark",
        release_sha[:12]: "Public auth page asset build does not match release",
    }
    for marker, message in required.items():
        if marker not in root_body:
            raise InfraError(message)
    if any(marker in root_body for marker in (
        "__OMNICIO_VERSION__", "__OMNICIO_BUILD__", "__OMNICIO_THEME_COLOR",
    )):
        raise InfraError("Public auth page contains unresolved release markers")
    versions = re.findall(r'<[^>]*\bdata-release-version\b[^>]*>([^<]+)</', root_body)
    if not versions or any(version != release_version() for version in versions):
        raise InfraError("Public page version does not match the reviewed package")


def verify_public_legal_versions(payload: dict[str, object]) -> None:
    expected_legal = {
        key: os.environ.get(f"LEGAL_{name.upper()}_VERSION", "").strip()
        for name, key in LEGAL_DOCUMENT_KEYS.items()
    }
    if not all(expected_legal.values()) or payload.get("legal_versions") != expected_legal:
        raise InfraError("Public legal versions do not match deployment config")


def verify_public_config(body: bytes, *, release_sha: str = "") -> None:
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise InfraError("Public auth config is not an object")
    verify_public_legal_versions(payload)
    release = payload.get("release")
    expected_build = release_sha[:12]
    if release_sha and (
        not isinstance(release, dict) or release.get("build") != expected_build
        or release.get("version") != release_version()
    ):
        raise InfraError("Public API version or build does not match the frontend release")

    if payload.get("mode") != "public" or payload.get("registration_enabled") is not True:
        raise InfraError("Public access mode does not match the email release contract")
    if "registration_max_users" in payload:
        raise InfraError("Public registration must not have a user capacity limit")
    if payload.get("auth_provider") != "email" or payload.get("auth_providers") != ["email"]:
        raise InfraError("Public auth provider must be email only")
    if payload.get("login_enabled") is not True:
        raise InfraError("Verified account login must remain enabled independently of SMTP")
    if (payload.get("email_domains") != ["gmail.com", "mail.ru", "xmail.ru"]
            or payload.get("password_min_length") != 15
            or payload.get("password_max_length") != 128
            or payload.get("email_code_digits") != 8):
        raise InfraError("Public email verification policy does not match the release contract")
    if any(payload.get(name) is not True for name in (
        "email_enabled", "registration_available", "password_reset_available",
    )):
        raise InfraError("Auth SMTP must be configured for public registration and recovery")


def verify_public_version_script(body: bytes, release_sha: str) -> None:
    """Parse the single generated assignment without a backtracking regex."""
    if len(body) > MAX_RELEASE_METADATA_BYTES:
        raise InfraError("Public application version metadata is too large")
    binding, separator, payload = body.decode().strip().partition("=")
    if not separator or binding.strip() != "window.OMNICIO_RELEASE":
        raise InfraError("Public application version assignment is invalid")
    try:
        metadata = json.loads(payload.strip().removesuffix(";").rstrip())
    except ValueError as exc:
        raise InfraError("Public application version metadata is malformed") from exc
    if metadata != {"version": release_version(), "build": release_sha[:12]}:
        raise InfraError("Public application version metadata does not match the release")


def verify_public_assets(context: ssl.SSLContext, release_sha: str) -> None:
    build = release_sha[:12]
    brand, content_type = fetch_public(BRAND_PUBLIC_MARK, context, expected_build=build)
    approved = (pathlib.Path(__file__).resolve().parents[2] / BRAND_SOURCE).read_bytes()
    if (content_type != PNG_CONTENT_TYPE
            or hashlib.sha256(brand).digest() != hashlib.sha256(approved).digest()):
        raise InfraError("Public approved brand mark verification failed")

    version_body, _ = fetch_public(VERSION_PUBLIC_PATH, context, expected_build=build)
    verify_public_version_script(version_body, release_sha)

    runtime_assets = (
        ("/assets/config.js", b"OMNICIO_CONFIG", JAVASCRIPT_CONTENT_TYPES),
        ("/assets/tokens.css", b"--browser-theme-dark", ("text/css",)),
        ("/assets/app.js", b"window.OmniUI", JAVASCRIPT_CONTENT_TYPES),
        ("/assets/workspace.js", b"window.OmniUI", JAVASCRIPT_CONTENT_TYPES),
        ("/assets/i18n.js", b"OMNICIO_I18N", JAVASCRIPT_CONTENT_TYPES),
        ("/assets/app.css", b"--sidebar", ("text/css",)),
        ("/assets/brand/earth-hero.png", b"\x89PNG\r\n\x1a\n", (PNG_CONTENT_TYPE,)),
        ("/assets/brand/auth-mountains.png", b"\x89PNG\r\n\x1a\n", (PNG_CONTENT_TYPE,)),
    )
    for path, marker, content_types in runtime_assets:
        body, content_type = fetch_public(f"{path}?build={build}", context, expected_build=build)
        if content_type not in content_types or marker not in body:
            raise InfraError(f"Public runtime asset verification failed: {path}")
        if path in {"/assets/app.js", "/assets/app.css", "/assets/workspace.js",
                    "/assets/i18n.js", "/assets/config.js", "/assets/tokens.css"} and (
            release_sha[:12].encode() not in body or b"__OMNICIO_BUILD__" in body
        ):
            raise InfraError(f"Public runtime asset build does not match release: {path}")


def verify_public(release_sha: str) -> None:
    context = ssl.create_default_context()
    try:
        root, _ = fetch_public("/", context, expected_build=release_sha[:12])
        verify_public_root(root, release_sha)
        verify_public_assets(context, release_sha)
        config, _ = fetch_public("/api/auth/config", context)
        verify_public_config(config, release_sha=release_sha)
        for path, marker in LEGAL_PAGES.items():
            body, content_type = fetch_public(path, context, expected_build=release_sha[:12])
            rendered = body.decode(errors="replace")
            if content_type != "text/html" or marker not in rendered:
                raise InfraError(f"Public legal page verification failed: {path}")
            if "__OMNICIO_OPERATOR_" in rendered or "__OMNICIO_BUILD__" in rendered:
                raise InfraError(f"Public legal page contains unresolved publication data: {path}")
            verify_legal_document_version(rendered, path)
    except (
        urllib.error.URLError, TimeoutError, ssl.SSLError, json.JSONDecodeError, UnicodeDecodeError,
    ) as exc:
        raise InfraError(
            f"Public application verification failed: {type(exc).__name__}"
        ) from exc


def reconcile(
    client: TimewebClient,
    *,
    server_name: str,
    server_comment: str,
    release_sha: str,
    repository_root: pathlib.Path,
    cluster_name: str,
    vpc_name: str,
    location: str,
    availability_zone: str,
) -> int:
    if not RELEASE_RE.fullmatch(release_sha):
        raise InfraError(INVALID_RELEASE_SHA)

    add_summary("## OmniCIO auth application deploy")
    validate_product_environment()
    validate_legal_documents(repository_root)
    server_summary = find_managed_server(
        client.get_servers(),
        name=server_name,
        comment=server_comment,
    )
    server_id = integer_value(server_summary["id"])
    server = client.get_server(server_id)

    vpc = find_vpc(
        client.get_vpcs(),
        name=vpc_name,
        location=location,
        availability_zone=availability_zone,
    )
    services = client.get_vpc_services(str(vpc["id"]))
    databases = [
        service
        for service in services
        if str(service.get("name") or "") == cluster_name
    ]
    if not databases:
        add_summary(
            "- Result: pending_database. Managed PostgreSQL is not present in "
            "the approved VPC; no SSH key, application, or Nginx configuration "
            "was changed."
        )
        set_output("status", "pending_database")
        return 0
    if len(databases) != 1:
        raise InfraError("Multiple same-name database services exist in the VPC")

    archive_b64 = build_release_archive(repository_root)

    with EphemeralSsh(
        client=client,
        server_id=server_id,
        server_ip=public_ipv4(server),
    ) as ssh:
        if not runtime_is_ready(ssh):
            add_summary(
                "- Result: pending_database. PostgreSQL/runtime secrets are "
                "not ready; no application or Nginx configuration was changed."
            )
            set_output("status", "pending_database")
            return 0

        preflight_product_environment(ssh)
        upload_release(ssh, archive_b64=archive_b64, release_sha=release_sha)

        try:
            write_product_environment(ssh, release_sha=release_sha)
            deploy_remote(ssh, release_sha=release_sha)
            for _ in range(6):
                try:
                    verify_public(release_sha)
                    break
                except InfraError:
                    time.sleep(5)
            else:
                raise InfraError("Public verification did not become healthy")

            commit_product_environment(ssh, release_sha=release_sha)
        except InfraError:
            rollback_remote(ssh, release_sha=release_sha)
            raise

    add_summary(
        f"- Result: app_ready. Release {release_sha[:12]} is healthy over HTTPS; "
        "public access is open, email/password login and SMTP configuration are ready. "
        "Existing profiles are preserved; legacy owners enroll from their active session. "
        "SMTP delivery and market-source coverage must be monitored separately."
    )
    set_output("status", "app_ready")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-name", required=True)
    parser.add_argument("--server-comment", required=True)
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--cluster-name", required=True)
    parser.add_argument("--vpc-name", required=True)
    parser.add_argument("--location", required=True)
    parser.add_argument("--availability-zone", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        validate_operation("apply", release_sha=args.release_sha)
        client = TimewebClient(os.environ.get("TIMEWEB_CLOUD_TOKEN", ""))
        return reconcile(
            client,
            server_name=args.server_name,
            server_comment=args.server_comment,
            release_sha=args.release_sha,
            repository_root=pathlib.Path(args.repository_root).resolve(),
            cluster_name=args.cluster_name,
            vpc_name=args.vpc_name,
            location=args.location,
            availability_zone=args.availability_zone,
        )
    except (
        InfraError,
        UpgradeBlocked,
        TimewebApiError,
        AmbiguousProviderError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
