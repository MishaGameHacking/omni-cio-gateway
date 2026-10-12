"""Small, auditable client for Timeweb Cloud AI Gateway.

The Android application never receives the gateway key. Model identifiers are
runtime configuration so the team can A/B-test or replace a provider without an
APK release. The client accepts only server-prepared messages and expects a JSON
object in return; it is not exposed as an end-user chat endpoint.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import httpx

try:
    from .ai_policy import AnalysisTier
except ImportError:  # pragma: no cover - uvicorn top-level import compatibility
    from ai_policy import AnalysisTier  # type: ignore[no-redef]

DEFAULT_BASE_URL = "https://api.timeweb.ai/v1"


class TimewebAIError(RuntimeError):
    """Base error safe to classify without exposing request contents."""

    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class TimewebAIConfigurationError(TimewebAIError):
    def __init__(self, code: str = "timeweb_ai_not_configured") -> None:
        super().__init__(code, retryable=False)


class TimewebAIUpstreamError(TimewebAIError):
    pass


class TimewebAIInvalidResponse(TimewebAIError):
    def __init__(self, code: str = "timeweb_ai_invalid_response") -> None:
        super().__init__(code, retryable=True)


@dataclass(frozen=True)
class TimewebAIConfig:
    api_key: str = field(repr=False)
    fast_model: str
    standard_model: str
    premium_model: str
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 45.0

    @classmethod
    def from_env(cls) -> "TimewebAIConfig":
        api_key = (
            os.getenv("TIMEWEB_AI_TOKEN")
            or os.getenv("TIMEWEB_CLOUD_API_KEY")
            or ""
        ).strip()
        return cls(
            api_key=api_key,
            fast_model=os.getenv("AI_MODEL_FAST", "").strip(),
            standard_model=os.getenv("AI_MODEL_STANDARD", "").strip(),
            premium_model=os.getenv("AI_MODEL_PREMIUM", "").strip(),
            base_url=(os.getenv("TIMEWEB_AI_BASE_URL", "").strip() or DEFAULT_BASE_URL).rstrip("/"),
            timeout_seconds=_positive_float(
                os.getenv("TIMEWEB_AI_TIMEOUT_SECONDS"),
                default=45.0,
            ),
        )

    def model_for(self, tier: AnalysisTier) -> str:
        if not self.api_key:
            raise TimewebAIConfigurationError("timeweb_ai_key_missing")
        model = {
            AnalysisTier.FAST: self.fast_model,
            AnalysisTier.STANDARD: self.standard_model,
            AnalysisTier.PREMIUM: self.premium_model,
        }.get(tier, "")
        if not model:
            raise TimewebAIConfigurationError(f"timeweb_ai_model_missing_{tier.value}")
        return model


@dataclass(frozen=True)
class TimewebAIUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class TimewebAIResult:
    model: str
    data: dict[str, Any]
    usage: TimewebAIUsage


class TimewebAIClient:
    def __init__(
        self,
        config: TimewebAIConfig | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config or TimewebAIConfig.from_env()
        self._transport = transport

    def complete_json(
        self,
        *,
        tier: AnalysisTier,
        messages: Sequence[Mapping[str, str]],
        max_output_tokens: int,
    ) -> TimewebAIResult:
        if tier is AnalysisTier.NONE:
            raise ValueError("AnalysisTier.NONE must never call an AI model")
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        if not messages:
            raise ValueError("messages must not be empty")

        model = self.config.model_for(tier)
        payload: dict[str, Any] = {
            "model": model,
            "messages": [dict(message) for message in messages],
            "stream": False,
        }
        if _uses_completion_token_parameter(model):
            # Timeweb documents that GPT-5-family models reject max_tokens and
            # temperature; newer GPT-6 aliases follow the same safe contract.
            payload["max_completion_tokens"] = max_output_tokens
        else:
            payload["max_tokens"] = max_output_tokens
            payload["temperature"] = 0.1

        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.config.timeout_seconds, connect=10.0),
                follow_redirects=False,
                transport=self._transport,
            ) as client:
                response = client.post(
                    f"{self.config.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException:
            raise TimewebAIUpstreamError(
                "timeweb_ai_timeout",
                retryable=True,
            ) from None
        except httpx.TransportError:
            raise TimewebAIUpstreamError(
                "timeweb_ai_connection_failed",
                retryable=True,
            ) from None

        _raise_for_status(response)
        try:
            response_payload = response.json()
        except (TypeError, ValueError):
            raise TimewebAIInvalidResponse() from None
        if not isinstance(response_payload, dict):
            raise TimewebAIInvalidResponse()

        content = _extract_content(response_payload)
        data = _parse_json_object(content)
        usage_payload = response_payload.get("usage")
        usage = TimewebAIUsage(
            prompt_tokens=_safe_non_negative_int(usage_payload, "prompt_tokens"),
            completion_tokens=_safe_non_negative_int(usage_payload, "completion_tokens"),
            total_tokens=_safe_non_negative_int(usage_payload, "total_tokens"),
        )
        returned_model = str(response_payload.get("model") or model)
        return TimewebAIResult(
            model=returned_model,
            data=data,
            usage=usage,
        )


def _positive_float(value: str | None, *, default: float) -> float:
    try:
        parsed = float(value) if value is not None else default
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _uses_completion_token_parameter(model: str) -> bool:
    normalized = model.lower().replace("_", "-")
    return "gpt-5" in normalized or "gpt-6" in normalized


def _raise_for_status(response: httpx.Response) -> None:
    status = int(response.status_code)
    if status in (401, 403):
        raise TimewebAIConfigurationError("timeweb_ai_access_denied")
    if status == 429:
        raise TimewebAIUpstreamError("timeweb_ai_rate_limited", retryable=True)
    if status in (408, 504):
        raise TimewebAIUpstreamError("timeweb_ai_timeout", retryable=True)
    if status >= 500:
        raise TimewebAIUpstreamError("timeweb_ai_unavailable", retryable=True)
    if status >= 400:
        raise TimewebAIConfigurationError("timeweb_ai_request_rejected")


def _extract_content(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise TimewebAIInvalidResponse()
    first = choices[0]
    if not isinstance(first, dict):
        raise TimewebAIInvalidResponse()
    message = first.get("message")
    if not isinstance(message, dict):
        raise TimewebAIInvalidResponse()
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                text_parts.append(part["text"])
        if text_parts:
            return "".join(text_parts)
    raise TimewebAIInvalidResponse()


def _parse_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        parsed = json.loads(stripped)
    except (TypeError, ValueError):
        raise TimewebAIInvalidResponse("timeweb_ai_non_json_response") from None
    if not isinstance(parsed, dict):
        raise TimewebAIInvalidResponse("timeweb_ai_non_object_response")
    return parsed


def _safe_non_negative_int(value: Any, key: str) -> int:
    if not isinstance(value, dict):
        return 0
    try:
        parsed = int(value.get(key, 0))
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)
