from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

if __package__:
    from .v10_jsonc import loads_jsonc
else:
    from v10_jsonc import loads_jsonc


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path(
    "docs/architecture/V10_TELEGRAM_PUBLIC_USER_LEGAL_PRIVACY_CONTRACT.json"
)
READINESS = Path(
    "docs/architecture/V10_TELEGRAM_PUBLIC_USER_ACTIVATION_READINESS_CONTRACT.json"
)
POLICY = Path("docs/legal/V10_OMNI_CIO_PRIVACY_POLICY_RU.md")
CONSENT = Path("docs/legal/V10_OMNI_CIO_PERSONAL_DATA_CONSENT_RU.md")
RUNBOOK = Path("docs/operations/V10_TELEGRAM_PUBLIC_USER_LEGAL_PRIVACY_RUNBOOK.md")
STATUS = Path("knowledge/17_V10_CURRENT_PROGRAM_STATUS.md")
WRANGLER = Path("wrangler.jsonc")

_EXPECTED_FLAGS = {
    "PUBLIC_MULTI_USER_ENABLED": "false",
    "OMNI_V10_TELEGRAM_LOGIN_ENABLED": "false",
    "OMNI_V10_VK_ID_LOGIN_ENABLED": "false",
}

_REQUIRED_BLOCKERS = {
    "RUSSIAN_PRIMARY_DATABASE_CUTOVER_NOT_ACCEPTED",
    "ROSKOMNADZOR_PROCESSING_NOTIFICATION_NOT_ACCEPTED",
    "CROSS_BORDER_PROCESSOR_FLOW_ASSESSMENT_NOT_ACCEPTED",
    "RU_HOSTED_DATA_SUBJECT_REQUEST_CHANNEL_NOT_ACCEPTED",
    "PUBLIC_PRIVACY_POLICY_NOT_DEPLOYED",
    "POST_ACTIVATION_REAL_USER_ISOLATION_EVIDENCE_NOT_AVAILABLE",
}


def _read(root: Path, relative: Path) -> str:
    try:
        return (root / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError("TELEGRAM_LEGAL_PRIVACY_SOURCE_UNREADABLE") from exc


def _load_json(root: Path, relative: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(_read(root, relative))
    except json.JSONDecodeError as exc:
        raise RuntimeError(code) from exc
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RuntimeError(code)
    return value


def _require(actual: object, expected: object, code: str) -> None:
    if actual != expected:
        raise RuntimeError(code)


def _validate_contract(contract: dict[str, Any]) -> None:
    _require(
        contract.get("schema"),
        "omni-cio.v10.telegram-public-user-legal-privacy.v1",
        "TELEGRAM_LEGAL_PRIVACY_SCHEMA_INVALID",
    )
    _require(
        contract.get("status"),
        "LEGAL_PRIVACY_ENGINEERING_READY_LIVE_ACTIVATION_BLOCKED",
        "TELEGRAM_LEGAL_PRIVACY_STATUS_INVALID",
    )
    _require(
        contract.get("capability_id"),
        "telegram_login",
        "TELEGRAM_LEGAL_PRIVACY_CAPABILITY_INVALID",
    )

    operator = _mapping(
        contract.get("operator"),
        "TELEGRAM_LEGAL_PRIVACY_OPERATOR_INVALID",
    )
    _require(
        operator.get("legal_form"),
        "NATURAL_PERSON_NPD_NOT_INDIVIDUAL_ENTREPRENEUR",
        "TELEGRAM_LEGAL_PRIVACY_OPERATOR_INVALID",
    )
    _require(
        operator.get("operator_identity_input_accepted"),
        True,
        "TELEGRAM_LEGAL_PRIVACY_OPERATOR_INVALID",
    )
    _require(
        operator.get("identity_document_required_in_repository"),
        False,
        "TELEGRAM_LEGAL_PRIVACY_OPERATOR_INVALID",
    )

    law = _mapping(
        contract.get("applicable_law"),
        "TELEGRAM_LEGAL_PRIVACY_LAW_INVALID",
    )
    for key in (
        "federal_law_152_fz",
        "article_18_5_russian_database_localization_required",
        "article_22_processing_notification_required",
        "article_12_cross_border_notification_required_if_transfer_occurs",
        "article_9_separate_consent_document_required_when_consent_is_used",
    ):
        _require(law.get(key), True, "TELEGRAM_LEGAL_PRIVACY_LAW_INVALID")
    _require(
        law.get("article_21_incident_notice_hours"),
        24,
        "TELEGRAM_LEGAL_PRIVACY_LAW_INVALID",
    )
    _require(
        law.get("article_21_internal_investigation_hours"),
        72,
        "TELEGRAM_LEGAL_PRIVACY_LAW_INVALID",
    )

    residency = _mapping(
        contract.get("current_data_residency"),
        "TELEGRAM_LEGAL_PRIVACY_LOCALIZATION_INVALID",
    )
    _require(
        residency.get("primary_database_provider"),
        "NEON_POSTGRESQL_18",
        "TELEGRAM_LEGAL_PRIVACY_LOCALIZATION_INVALID",
    )
    _require(
        residency.get("primary_database_region"),
        "FRANKFURT",
        "TELEGRAM_LEGAL_PRIVACY_LOCALIZATION_INVALID",
    )
    for key in (
        "russian_localization_accepted",
        "live_russian_user_collection_allowed",
        "candidate_is_production_authority",
    ):
        _require(
            residency.get(key),
            False,
            "TELEGRAM_LEGAL_PRIVACY_LOCALIZATION_INVALID",
        )
    _require(
        residency.get("required_before_activation"),
        "RU_PG_D_PRODUCTION_DATABASE_CUTOVER_TO_RUSSIAN_FEDERATION",
        "TELEGRAM_LEGAL_PRIVACY_LOCALIZATION_INVALID",
    )

    regulator = _mapping(
        contract.get("regulator_and_public_notice"),
        "TELEGRAM_LEGAL_PRIVACY_REGULATOR_INVALID",
    )
    for key in (
        "roskomnadzor_processing_notification_accepted",
        "cross_border_notification_accepted",
        "public_privacy_policy_deployed",
        "personal_data_request_channel_accepted",
    ):
        _require(
            regulator.get(key),
            False,
            "TELEGRAM_LEGAL_PRIVACY_REGULATOR_INVALID",
        )

    gate = _mapping(
        contract.get("activation_gate"),
        "TELEGRAM_LEGAL_PRIVACY_GATE_INVALID",
    )
    _require(gate.get("accepted"), False, "TELEGRAM_LEGAL_PRIVACY_GATE_INVALID")
    blockers = gate.get("blocking_conditions")
    if not isinstance(blockers, list) or set(blockers) != _REQUIRED_BLOCKERS:
        raise RuntimeError("TELEGRAM_LEGAL_PRIVACY_GATE_INVALID")


def _validate_public_docs(root: Path) -> None:
    policy = _read(root, POLICY)
    consent = _read(root, CONSENT)
    runbook = _read(root, RUNBOOK)
    for marker in (
        "# Политика Omni-CIO в отношении обработки персональных данных",
        "**Статус:** ПРЕДЗАПУСКОВАЯ РЕДАКЦИЯ",
        "## 3. Цели и правовые основания",
        "## 7. Локализация и внешние поставщики",
        "## 9. Условия публикации финальной политики",
    ):
        if marker not in policy:
            raise RuntimeError("TELEGRAM_LEGAL_PRIVACY_POLICY_DRIFT")
    for marker in (
        "# Отдельное согласие на обработку персональных данных Omni-CIO",
        "**Статус:** ПРЕДЗАПУСКОВОЙ ШАБЛОН",
        "## 1. Граница согласия",
        "## 3. Отзыв",
    ):
        if marker not in consent:
            raise RuntimeError("TELEGRAM_LEGAL_PRIVACY_CONSENT_DRIFT")
    for marker in (
        "# V10 Telegram Public User Legal / Privacy Activation Runbook",
        "Status: **FOCUSED CAPABILITY ACTIVATION GATE / LIVE REGISTRATION BLOCKED**",
        "## 2. Current hard localization blocker",
        "## 6. Regulator gates",
        "## 7. Activation boundary",
    ):
        if marker not in runbook:
            raise RuntimeError("TELEGRAM_LEGAL_PRIVACY_RUNBOOK_DRIFT")


def _validate_current_state(root: Path) -> None:
    status = _read(root, STATUS)
    for marker in (
        "current Neon production authority remains accepted until an explicit later cutover",
        "RU-PG-C remains locked until RU-PG-B",
    ):
        if marker not in status:
            raise RuntimeError("TELEGRAM_LEGAL_PRIVACY_CURRENT_STATE_DRIFT")

    try:
        wrangler = loads_jsonc(_read(root, WRANGLER))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("TELEGRAM_LEGAL_PRIVACY_WRANGLER_INVALID") from exc
    if not isinstance(wrangler, dict):
        raise RuntimeError("TELEGRAM_LEGAL_PRIVACY_WRANGLER_INVALID")
    production = wrangler.get("vars")
    env = wrangler.get("env")
    if not isinstance(production, dict) or not isinstance(env, dict):
        raise RuntimeError("TELEGRAM_LEGAL_PRIVACY_FLAG_DRIFT")
    staging = env.get("staging")
    if not isinstance(staging, dict) or not isinstance(staging.get("vars"), dict):
        raise RuntimeError("TELEGRAM_LEGAL_PRIVACY_FLAG_DRIFT")
    for key, expected in _EXPECTED_FLAGS.items():
        if production.get(key) != expected or staging["vars"].get(key) != expected:
            raise RuntimeError("TELEGRAM_LEGAL_PRIVACY_PREMATURE_ACTIVATION")


def _validate_readiness_link(
    root: Path,
    contract: dict[str, Any],
) -> None:
    readiness = _load_json(
        root,
        READINESS,
        "TELEGRAM_LEGAL_PRIVACY_READINESS_INVALID",
    )
    legal = _mapping(
        readiness.get("legal_privacy_gate"),
        "TELEGRAM_LEGAL_PRIVACY_READINESS_INVALID",
    )
    _require(
        legal.get("accepted"),
        False,
        "TELEGRAM_LEGAL_PRIVACY_READINESS_INVALID",
    )
    _require(
        legal.get("status"),
        "OPERATOR_IDENTITY_ACCEPTED_DATA_RESIDENCY_AND_REGULATORY_GATES_OPEN",
        "TELEGRAM_LEGAL_PRIVACY_READINESS_INVALID",
    )
    _require(
        legal.get("contract_path"),
        str(CONTRACT).replace("\\", "/"),
        "TELEGRAM_LEGAL_PRIVACY_READINESS_INVALID",
    )
    _require(
        legal.get("contract_schema"),
        contract.get("schema"),
        "TELEGRAM_LEGAL_PRIVACY_READINESS_INVALID",
    )
    resolved = legal.get("resolved_inputs")
    if (
        not isinstance(resolved, list)
        or "operator_controller_identity_and_contact" not in resolved
    ):
        raise RuntimeError("TELEGRAM_LEGAL_PRIVACY_READINESS_INVALID")
    readiness_blockers = legal.get("blocking_conditions")
    activation = _mapping(
        contract.get("activation_gate"),
        "TELEGRAM_LEGAL_PRIVACY_READINESS_INVALID",
    )
    contract_blockers = activation.get("blocking_conditions")
    if (
        not isinstance(readiness_blockers, list)
        or not isinstance(contract_blockers, list)
        or set(readiness_blockers) != set(contract_blockers)
    ):
        raise RuntimeError("TELEGRAM_LEGAL_PRIVACY_READINESS_INVALID")


def validate(root: Path = ROOT) -> None:
    contract = _load_json(
        root,
        CONTRACT,
        "TELEGRAM_LEGAL_PRIVACY_CONTRACT_INVALID",
    )
    _validate_contract(contract)
    _validate_public_docs(root)
    _validate_current_state(root)
    _validate_readiness_link(root, contract)


def main() -> int:
    try:
        validate()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        "V10 Telegram legal/privacy pre-activation contract passed; "
        "Russian DB/regulatory/cross-border/contact gates remain fail-closed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
