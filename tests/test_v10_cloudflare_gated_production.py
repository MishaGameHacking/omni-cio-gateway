from __future__ import annotations

from typing import Any, cast
import unittest
from unittest.mock import patch

import scripts.bootstrap_v10_cloudflare_builds as builds
import scripts.run_v10_cloudflare_gated_production as production


_SHA = "a" * 40
_ACCOUNT_ID = "b" * 32
_TRIGGER_UUID = "11111111-2222-3333-4444-555555555555"
_BUILD_UUID = "22222222-3333-4444-5555-666666666666"
_STALE_BUILD_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_WORKER_TAG = "c" * 32
_CONNECTION_UUID = "33333333-4444-5555-6666-777777777777"
_BUILD_TOKEN_UUID = "44444444-5555-6666-7777-888888888888"


class CloudflareGatedProductionTests(unittest.TestCase):
    def test_build_identity_requires_main_and_production_deploy_command(self) -> None:
        good = {
            "build_outcome": "success",
            "status": "stopped",
            "commit_hash": _SHA,
            "build_trigger_metadata": {
                "commit_hash": _SHA,
                "branch": "main",
                "build_command": "npm run build",
                "deploy_command": "npm run cloudflare:deploy",
            },
        }
        production._assert_build_identity(good, _SHA)

        for key, value in (
            ("branch", "system/cloudflare-public-product"),
            ("deploy_command", "npm run cloudflare:deploy:staging"),
        ):
            with self.subTest(key=key):
                bad = {
                    **good,
                    "build_trigger_metadata": dict(good["build_trigger_metadata"]),
                }
                bad["build_trigger_metadata"][key] = value
                with self.assertRaisesRegex(
                    RuntimeError,
                    "CLOUDFLARE_PRODUCTION_BUILD_IDENTITY_DRIFT",
                ):
                    production._assert_build_identity(bad, _SHA)

    def test_unknown_production_trigger_is_not_deleted_or_reused(self) -> None:
        api = cast(builds.CloudflareApi, object())
        with patch.object(
            production,
            "_existing_triggers",
            return_value=[{"trigger_name": "unexpected"}],
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_PRODUCTION_AUTODEPLOY_FORBIDDEN",
            ):
                production._stale_owned_trigger_uuid(
                    api,
                    worker_tag=_WORKER_TAG,
                    connection_uuid=_CONNECTION_UUID,
                    desired={},
                )

    def test_stale_owned_gated_trigger_is_validated_without_early_delete(self) -> None:
        api = cast(builds.CloudflareApi, object())
        with (
            patch.object(
                production,
                "_existing_triggers",
                return_value=[{"trigger_name": production._PRODUCTION_TRIGGER_NAME}],
            ),
            patch.object(production, "_validate_trigger", return_value=_TRIGGER_UUID),
            patch.object(production, "_delete_trigger") as delete,
        ):
            trigger_uuid = production._stale_owned_trigger_uuid(
                api,
                worker_tag=_WORKER_TAG,
                connection_uuid=_CONNECTION_UUID,
                desired={},
            )
        self.assertEqual(trigger_uuid, _TRIGGER_UUID)
        delete.assert_not_called()

    def test_unknown_trigger_blocks_before_any_stale_build_cancellation(self) -> None:
        api = cast(builds.CloudflareApi, object())
        with (
            patch.object(
                production,
                "_stale_owned_trigger_uuid",
                side_effect=builds.BootstrapStopped(
                    "CLOUDFLARE_PRODUCTION_AUTODEPLOY_FORBIDDEN"
                ),
            ),
            patch.object(production, "_cancel_nonterminal_builds") as cancel,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_PRODUCTION_AUTODEPLOY_FORBIDDEN",
            ):
                production._quarantine_provider_activity(
                    api,
                    worker_tag=_WORKER_TAG,
                    connection_uuid=_CONNECTION_UUID,
                    build_token_uuid=_BUILD_TOKEN_UUID,
                )
        cancel.assert_not_called()

    def test_quarantine_confirms_builds_terminal_before_deleting_owned_trigger(
        self,
    ) -> None:
        api = cast(builds.CloudflareApi, object())
        events: list[str] = []

        def cancel(_api: builds.CloudflareApi, worker_tag: str) -> int:
            self.assertEqual(worker_tag, _WORKER_TAG)
            events.append("cancel")
            return 1

        def delete(_api: builds.CloudflareApi, trigger_uuid: str | None) -> None:
            self.assertEqual(trigger_uuid, _TRIGGER_UUID)
            events.append("delete")

        with (
            patch.object(
                production,
                "_stale_owned_trigger_uuid",
                return_value=_TRIGGER_UUID,
            ),
            patch.object(
                production,
                "_cancel_nonterminal_builds",
                side_effect=cancel,
            ),
            patch.object(production, "_delete_trigger", side_effect=delete),
        ):
            self.assertEqual(
                production._quarantine_provider_activity(
                    api,
                    worker_tag=_WORKER_TAG,
                    connection_uuid=_CONNECTION_UUID,
                    build_token_uuid=_BUILD_TOKEN_UUID,
                ),
                (1, 1),
            )
        self.assertEqual(events, ["cancel", "delete"])

    def test_cancel_terminal_race_accepts_only_confirmed_terminal_state(self) -> None:
        class Api:
            account_id = _ACCOUNT_ID

            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []
                self.status_reads = 0

            def request(self, method: str, path: str, **kwargs: Any) -> object:
                if kwargs:
                    raise AssertionError(kwargs)
                self.calls.append((method, path))
                if method == "GET":
                    self.status_reads += 1
                    if self.status_reads == 1:
                        return {"build_outcome": None, "status": "running"}
                    return {"build_outcome": "success", "status": "stopped"}
                if method == "PUT":
                    raise builds.BootstrapStopped(
                        "CLOUDFLARE_API_HTTP_ERROR",
                        status=409,
                    )
                raise AssertionError((method, path))

        api = Api()
        with patch.object(production.time, "sleep") as sleep:
            terminal = production._cancel_if_nonterminal(
                cast(builds.CloudflareApi, api),
                _BUILD_UUID,
            )
        self.assertEqual(terminal, {"build_outcome": "success", "status": "stopped"})
        sleep.assert_not_called()
        self.assertEqual([method for method, _ in api.calls], ["GET", "PUT", "GET"])

    def test_cancel_race_remains_fail_closed_after_bounded_confirmation(self) -> None:
        class Api:
            account_id = _ACCOUNT_ID

            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def request(self, method: str, path: str, **kwargs: Any) -> object:
                if kwargs:
                    raise AssertionError(kwargs)
                self.calls.append((method, path))
                if method == "GET":
                    return {"build_outcome": None, "status": "running"}
                if method == "PUT":
                    return {}
                raise AssertionError((method, path))

        api = Api()
        with patch.object(production.time, "sleep") as sleep:
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_PRODUCTION_BUILD_CANCEL_RACE",
            ):
                production._cancel_if_nonterminal(
                    cast(builds.CloudflareApi, api),
                    _BUILD_UUID,
                )
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            list(production._CANCEL_CONFIRM_DELAYS),
        )

    def test_stale_build_success_race_fails_closed_before_trigger_delete(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_PRODUCTION_STALE_BUILD_SUCCESS_RACE",
        ):
            production._assert_stale_build_safely_terminal(
                {"build_outcome": "success", "status": "stopped"}
            )

    def test_stale_build_stopped_without_outcome_remains_unconfirmed(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "CLOUDFLARE_PRODUCTION_STALE_BUILD_OUTCOME_UNCONFIRMED",
        ):
            production._assert_stale_build_safely_terminal(
                {"build_outcome": None, "status": "stopped"}
            )

    def test_cancel_nonterminal_rejects_unclassified_provider_failure(self) -> None:
        class Api:
            account_id = _ACCOUNT_ID

            def request(self, method: str, path: str, **kwargs: Any) -> object:
                if kwargs:
                    raise AssertionError(kwargs)
                if method == "GET":
                    return {"build_outcome": None, "status": "running"}
                if method == "PUT":
                    raise builds.BootstrapStopped(
                        "CLOUDFLARE_API_HTTP_ERROR",
                        status=404,
                    )
                raise AssertionError((method, path))

        with self.assertRaisesRegex(RuntimeError, "CLOUDFLARE_API_HTTP_ERROR"):
            production._cancel_if_nonterminal(
                cast(builds.CloudflareApi, Api()),
                _BUILD_UUID,
            )

    def test_quarantine_cancels_nonterminal_production_builds(self) -> None:
        api = cast(builds.CloudflareApi, object())
        rows = [
            {
                "build_uuid": _BUILD_UUID,
                "build_outcome": "success",
                "status": "stopped",
            },
            {
                "build_uuid": _STALE_BUILD_UUID,
                "build_outcome": None,
                "status": "running",
            },
        ]
        cancelled: list[str] = []

        def cancel(
            _api: builds.CloudflareApi,
            build_uuid: str | None,
        ) -> dict[str, Any]:
            if build_uuid is None:
                raise AssertionError("build uuid required")
            cancelled.append(build_uuid)
            return {"build_outcome": "cancelled", "status": "stopped"}

        with (
            patch.object(builds, "_builds_for_worker", return_value=rows),
            patch.object(production, "_cancel_if_nonterminal", side_effect=cancel),
        ):
            count = production._cancel_nonterminal_builds(api, _WORKER_TAG)
        self.assertEqual(count, 1)
        self.assertEqual(cancelled, [_STALE_BUILD_UUID])

    def test_quarantine_only_uses_same_authority_and_provider_cleanup(self) -> None:
        api = cast(builds.CloudflareApi, object())

        def required(name: str) -> str:
            return "token" if name == "CLOUDFLARE_API_TOKEN" else _ACCOUNT_ID

        with (
            patch.object(production, "_assert_exact_head", return_value=_SHA),
            patch.object(builds, "_required_env", side_effect=required),
            patch.object(builds, "CloudflareApi", return_value=api),
            patch.object(
                production,
                "_prepare_authority",
                return_value=(_WORKER_TAG, _CONNECTION_UUID, _BUILD_TOKEN_UUID),
            ),
            patch.object(
                production,
                "_quarantine_provider_activity",
                return_value=(2, 1),
            ) as quarantine,
        ):
            self.assertEqual(production.quarantine(_SHA), (2, 1))
        quarantine.assert_called_once_with(
            api,
            worker_tag=_WORKER_TAG,
            connection_uuid=_CONNECTION_UUID,
            build_token_uuid=_BUILD_TOKEN_UUID,
        )

    def test_run_cleans_trigger_after_terminal_build_failure(self) -> None:
        events: list[str] = []

        class Api:
            account_id = _ACCOUNT_ID

            def request(self, *args: Any, **kwargs: Any) -> object:
                del args, kwargs
                return {}

        api = cast(builds.CloudflareApi, Api())

        def quarantine(*args: Any, **kwargs: Any) -> tuple[int, int]:
            del args, kwargs
            events.append("quarantine")
            return 0, 0

        def create(*args: Any, **kwargs: Any) -> str:
            del args, kwargs
            events.append("create")
            return _TRIGGER_UUID

        def start(*args: Any, **kwargs: Any) -> str:
            del args, kwargs
            events.append("start")
            return _BUILD_UUID

        def wait(*args: Any, **kwargs: Any) -> None:
            del args, kwargs
            events.append("wait")
            raise builds.BootstrapStopped("CLOUDFLARE_PRODUCTION_BUILD_FAILED")

        def cancel(*args: Any, **kwargs: Any) -> None:
            del args, kwargs
            events.append("cancel")

        def delete(*args: Any, **kwargs: Any) -> None:
            del args, kwargs
            events.append("delete")

        def required(name: str) -> str:
            return "token" if name == "CLOUDFLARE_API_TOKEN" else _ACCOUNT_ID

        with (
            patch.object(production, "_assert_exact_head", return_value=_SHA),
            patch.object(builds, "_required_env", side_effect=required),
            patch.object(builds, "CloudflareApi", return_value=api),
            patch.object(
                production,
                "_prepare_authority",
                return_value=(_WORKER_TAG, _CONNECTION_UUID, _BUILD_TOKEN_UUID),
            ),
            patch.object(
                production,
                "_quarantine_provider_activity",
                side_effect=quarantine,
            ),
            patch.object(production, "_create_trigger", side_effect=create),
            patch.object(production, "_start_build", side_effect=start),
            patch.object(production, "_wait_build", side_effect=wait),
            patch.object(production, "_cancel_if_nonterminal", side_effect=cancel),
            patch.object(production, "_delete_trigger", side_effect=delete),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "CLOUDFLARE_PRODUCTION_BUILD_FAILED",
            ):
                production.run(_SHA)
        self.assertEqual(
            events,
            ["quarantine", "create", "start", "wait", "cancel", "delete"],
        )


if __name__ == "__main__":
    unittest.main()
