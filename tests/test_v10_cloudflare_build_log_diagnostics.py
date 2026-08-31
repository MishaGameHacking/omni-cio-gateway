from __future__ import annotations

from typing import Any, cast
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds


_BUILD_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class _EventuallyReadyLogsApi:
    account_id = "a" * 32

    def __init__(self) -> None:
        self.calls = 0

    def request(self, method: str, path: str) -> Any:
        if method != "GET" or not path.endswith("/logs"):
            raise AssertionError((method, path))
        self.calls += 1
        if self.calls < 3:
            raise builds.BootstrapStopped(
                "CLOUDFLARE_API_HTTP_ERROR",
                status=404,
            )
        return {
            "lines": [
                [
                    0,
                    "Failed: The build token selected for this build has been "
                    "deleted or rolled and cannot be used for this build.",
                ]
            ],
            "cursor": None,
            "truncated": False,
        }


class _PersistentLogsFailureApi:
    account_id = "a" * 32

    def __init__(self, code: str, status: int) -> None:
        self.code = code
        self.status = status
        self.calls = 0

    def request(self, method: str, path: str) -> Any:
        if method != "GET" or not path.endswith("/logs"):
            raise AssertionError((method, path))
        self.calls += 1
        raise builds.BootstrapStopped(self.code, status=self.status)


class _SequenceLogsApi:
    account_id = "a" * 32

    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self.pages = pages
        self.paths: list[str] = []

    def request(self, method: str, path: str) -> Any:
        if method != "GET" or "/logs" not in path:
            raise AssertionError((method, path))
        self.paths.append(path)
        index = len(self.paths) - 1
        if index >= len(self.pages):
            raise AssertionError("unexpected build-log page request")
        return self.pages[index]


class CloudflareBuildLogDiagnosticTests(unittest.TestCase):
    def test_failed_build_logs_retry_bounded_not_found_then_classify(self) -> None:
        raw_api = _EventuallyReadyLogsApi()
        api = cast(builds.CloudflareApi, raw_api)
        with patch.object(builds.time, "sleep") as sleep:
            diagnostic = builds._build_failure_diagnostic(api, _BUILD_UUID)

        self.assertEqual(diagnostic, "CLOUDFLARE_BUILD_TOKEN_STALE")
        self.assertEqual(raw_api.calls, 3)
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            list(builds._BUILD_LOG_NOT_READY_RETRY_DELAYS[:2]),
        )

    def test_failed_build_log_retry_is_narrow_to_http_not_found(self) -> None:
        raw_api = _PersistentLogsFailureApi(
            "CLOUDFLARE_API_TOKEN_INSUFFICIENT",
            403,
        )
        api = cast(builds.CloudflareApi, raw_api)
        with patch.object(builds.time, "sleep") as sleep:
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_API_TOKEN_INSUFFICIENT",
            ):
                builds._build_failure_diagnostic(api, _BUILD_UUID)

        self.assertEqual(raw_api.calls, 1)
        sleep.assert_not_called()

    def test_persistent_log_not_found_is_sanitized_and_bounded(self) -> None:
        raw_api = _PersistentLogsFailureApi("CLOUDFLARE_API_HTTP_ERROR", 404)
        api = cast(builds.CloudflareApi, raw_api)
        with (
            patch.object(builds.time, "sleep") as sleep,
            patch("builtins.print") as printer,
        ):
            diagnostic = builds._safe_build_failure_diagnostic(api, _BUILD_UUID)

        self.assertEqual(diagnostic, "CLOUDFLARE_BUILD_LOG_DIAGNOSTIC_UNAVAILABLE")
        self.assertEqual(
            raw_api.calls,
            len(builds._BUILD_LOG_NOT_READY_RETRY_DELAYS) + 1,
        )
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            list(builds._BUILD_LOG_NOT_READY_RETRY_DELAYS),
        )
        rendered = [str(call.args[0]) for call in printer.call_args_list if call.args]
        self.assertIn(
            "CLOUDFLARE_BUILD_LOG_DIAGNOSTIC=UNAVAILABLE "
            "code=CLOUDFLARE_API_HTTP_ERROR status=404",
            rendered,
        )
        self.assertIn(
            "CLOUDFLARE_BUILD_FAILURE_DIAGNOSTIC="
            "CLOUDFLARE_BUILD_LOG_DIAGNOSTIC_UNAVAILABLE",
            rendered,
        )

    def test_optional_cloudflare_log_lines_can_be_omitted(self) -> None:
        self.assertEqual(
            builds._build_log_messages({"cursor": None, "truncated": False}),
            (),
        )

    def test_untruncated_page_does_not_follow_advisory_cursor(self) -> None:
        raw_api = _SequenceLogsApi(
            [
                {
                    "lines": [
                        [
                            0,
                            "Failed: The build token selected for this build has been "
                            "deleted or rolled and cannot be used for this build.",
                        ]
                    ],
                    "cursor": "provider-terminal-cursor",
                    "truncated": False,
                }
            ]
        )
        api = cast(builds.CloudflareApi, raw_api)

        diagnostic = builds._build_failure_diagnostic(api, _BUILD_UUID)

        self.assertEqual(diagnostic, "CLOUDFLARE_BUILD_TOKEN_STALE")
        self.assertEqual(len(raw_api.paths), 1)
        self.assertNotIn("?cursor=", raw_api.paths[0])

    def test_truncated_page_follows_encoded_cursor_until_terminal_page(self) -> None:
        raw_api = _SequenceLogsApi(
            [
                {
                    "lines": [[0, "starting failed build diagnostics"]],
                    "cursor": "page/1+token==",
                    "truncated": True,
                },
                {
                    "lines": [
                        [
                            1,
                            "Failed: The build token selected for this build has been "
                            "deleted or rolled and cannot be used for this build.",
                        ]
                    ],
                    "cursor": "terminal-cursor-is-not-followed",
                    "truncated": False,
                },
            ]
        )
        api = cast(builds.CloudflareApi, raw_api)

        diagnostic = builds._build_failure_diagnostic(api, _BUILD_UUID)

        self.assertEqual(diagnostic, "CLOUDFLARE_BUILD_TOKEN_STALE")
        self.assertEqual(len(raw_api.paths), 2)
        self.assertNotIn("?cursor=", raw_api.paths[0])
        self.assertTrue(raw_api.paths[1].endswith("?cursor=page%2F1%2Btoken%3D%3D"))

    def test_missing_optional_truncated_flag_does_not_invent_pagination(self) -> None:
        raw_api = _SequenceLogsApi(
            [
                {
                    "lines": [[0, "generic build command failure"]],
                    "cursor": "advisory-cursor",
                }
            ]
        )
        api = cast(builds.CloudflareApi, raw_api)

        diagnostic = builds._build_failure_diagnostic(api, _BUILD_UUID)

        self.assertEqual(diagnostic, "CLOUDFLARE_BUILD_COMMAND_PHASE_FAILED")
        self.assertEqual(len(raw_api.paths), 1)

    def test_truncated_flag_must_be_boolean_when_present(self) -> None:
        raw_api = _SequenceLogsApi(
            [{"lines": [], "cursor": "cursor", "truncated": "false"}]
        )
        api = cast(builds.CloudflareApi, raw_api)

        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_BUILD_LOG_TRUNCATED_INVALID",
        ):
            builds._build_failure_diagnostic(api, _BUILD_UUID)

    def test_truncated_page_requires_valid_non_repeating_cursor(self) -> None:
        invalid_pages = (
            {"lines": [], "cursor": None, "truncated": True},
            {"lines": [], "cursor": "", "truncated": True},
            {"lines": [], "cursor": 7, "truncated": True},
            {
                "lines": [],
                "cursor": "x" * (builds._BUILD_LOG_MAX_CURSOR_CHARS + 1),
                "truncated": True,
            },
        )
        for page in invalid_pages:
            with self.subTest(cursor=page["cursor"]):
                raw_api = _SequenceLogsApi([page])
                api = cast(builds.CloudflareApi, raw_api)
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_BUILD_LOG_CURSOR_INVALID",
                ):
                    builds._build_failure_diagnostic(api, _BUILD_UUID)

        repeated = _SequenceLogsApi(
            [
                {"lines": [], "cursor": "same", "truncated": True},
                {"lines": [], "cursor": "same", "truncated": True},
            ]
        )
        api = cast(builds.CloudflareApi, repeated)
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_BUILD_LOG_CURSOR_INVALID",
        ):
            builds._build_failure_diagnostic(api, _BUILD_UUID)
        self.assertEqual(len(repeated.paths), 2)

    def test_log_pagination_exhaustion_fails_closed(self) -> None:
        raw_api = _SequenceLogsApi(
            [
                {"lines": [[0, "page one"]], "cursor": "one", "truncated": True},
                {"lines": [[1, "page two"]], "cursor": "two", "truncated": True},
            ]
        )
        api = cast(builds.CloudflareApi, raw_api)
        with patch.object(builds, "_BUILD_LOG_MAX_PAGES", 2):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_BUILD_LOG_PAGINATION_EXHAUSTED",
            ):
                builds._build_failure_diagnostic(api, _BUILD_UUID)

        self.assertEqual(len(raw_api.paths), 2)


if __name__ == "__main__":
    unittest.main()
