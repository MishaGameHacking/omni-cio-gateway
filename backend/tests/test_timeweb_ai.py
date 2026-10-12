from __future__ import annotations

import json
import unittest

import httpx

from backend.ai_policy import AnalysisTier
from backend.timeweb_ai import (
    TimewebAIClient,
    TimewebAIConfig,
    TimewebAIConfigurationError,
    TimewebAIInvalidResponse,
    TimewebAIUpstreamError,
)


class TimewebAIClientTests(unittest.TestCase):
    def config(
        self,
        *,
        fast: str = "google/gemini-fast",
        standard: str = "deepseek/standard",
        premium: str = "openai/gpt-5.4",
    ) -> TimewebAIConfig:
        return TimewebAIConfig(
            api_key="server-secret",
            fast_model=fast,
            standard_model=standard,
            premium_model=premium,
            base_url="https://api.timeweb.ai/v1",
            timeout_seconds=12,
        )

    def test_fast_model_uses_standard_openai_parameters_and_parses_json(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["authorization"] = request.headers.get("authorization")
            captured["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "model": "google/gemini-fast",
                    "choices": [
                        {
                            "message": {
                                "content": "```json\n{\"severity\":\"info\"}\n```"
                            }
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 12,
                        "total_tokens": 112,
                    },
                },
            )

        client = TimewebAIClient(
            self.config(),
            transport=httpx.MockTransport(handler),
        )
        result = client.complete_json(
            tier=AnalysisTier.FAST,
            messages=({"role": "user", "content": "structured facts"},),
            max_output_tokens=300,
        )

        self.assertEqual(captured["url"], "https://api.timeweb.ai/v1/chat/completions")
        self.assertEqual(captured["authorization"], "Bearer server-secret")
        self.assertEqual(captured["payload"]["model"], "google/gemini-fast")
        self.assertEqual(captured["payload"]["max_tokens"], 300)
        self.assertEqual(captured["payload"]["temperature"], 0.1)
        self.assertNotIn("max_completion_tokens", captured["payload"])
        self.assertEqual(result.data, {"severity": "info"})
        self.assertEqual(result.usage.total_tokens, 112)
        self.assertNotIn("server-secret", repr(self.config()))

    def test_gpt_5_family_uses_max_completion_tokens_without_temperature(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured.update(json.loads(request.content))
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": "{\"severity\":\"critical\"}"}}
                    ],
                    "usage": {},
                },
            )

        client = TimewebAIClient(
            self.config(premium="openai/gpt-5.4-mini"),
            transport=httpx.MockTransport(handler),
        )
        client.complete_json(
            tier=AnalysisTier.PREMIUM,
            messages=({"role": "user", "content": "risk"},),
            max_output_tokens=1_200,
        )

        self.assertEqual(captured["max_completion_tokens"], 1_200)
        self.assertNotIn("max_tokens", captured)
        self.assertNotIn("temperature", captured)

    def test_missing_model_configuration_stops_before_network_call(self) -> None:
        calls = 0

        def handler(_: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(200, json={})

        client = TimewebAIClient(
            self.config(fast=""),
            transport=httpx.MockTransport(handler),
        )
        with self.assertRaises(TimewebAIConfigurationError) as raised:
            client.complete_json(
                tier=AnalysisTier.FAST,
                messages=({"role": "user", "content": "facts"},),
                max_output_tokens=100,
            )
        self.assertEqual(raised.exception.code, "timeweb_ai_model_missing_fast")
        self.assertEqual(calls, 0)

    def test_rate_limit_is_retryable(self) -> None:
        client = TimewebAIClient(
            self.config(),
            transport=httpx.MockTransport(lambda _: httpx.Response(429)),
        )
        with self.assertRaises(TimewebAIUpstreamError) as raised:
            client.complete_json(
                tier=AnalysisTier.FAST,
                messages=({"role": "user", "content": "facts"},),
                max_output_tokens=100,
            )
        self.assertEqual(raised.exception.code, "timeweb_ai_rate_limited")
        self.assertTrue(raised.exception.retryable)

    def test_non_json_model_output_is_rejected(self) -> None:
        client = TimewebAIClient(
            self.config(),
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json={
                        "choices": [
                            {"message": {"content": "I cannot return JSON today"}}
                        ]
                    },
                )
            ),
        )
        with self.assertRaises(TimewebAIInvalidResponse):
            client.complete_json(
                tier=AnalysisTier.STANDARD,
                messages=({"role": "user", "content": "facts"},),
                max_output_tokens=300,
            )


if __name__ == "__main__":
    unittest.main()
