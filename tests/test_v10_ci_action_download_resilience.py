from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

CURRENT_SELF_HOSTED_AUTHORITY_WORKFLOWS = (
    "regression-shield.yml",
    "self-hosted-windows-smoke.yml",
    "v10-engineering-governance.yml",
    "v10-pr-fast-checks.yml",
    "v10-toolchain-compat.yml",
    "v10-live-gateway-authority-contract.yml",
    "v10-wp6-identity-audit.yml",
    "v10-wp15-live-web-support-audit.yml",
    "v10-wp16-web-design-system-audit.yml",
    "v10-wp17-application-shell-audit.yml",
    "v10-wp18-portfolio-dashboard-audit.yml",
    "v10-wp19-watchtower-incidents-audit.yml",
    "v10-wp20-research-dossier-audit.yml",
    "v10-wp21-decision-risk-plan-audit.yml",
    "v10-wp22-system-admin-audit.yml",
    "v10-wp22a-clientless-access-audit.yml",
    "v10-wp22a-phase2-product-auth-audit.yml",
)

BLOCKER_DEPENDENCY_CLOSED_RETRY_WORKFLOWS = (
    "regression-shield.yml",
    "self-hosted-windows-smoke.yml",
    "v10-engineering-governance.yml",
    "v10-pr-fast-checks.yml",
    "v10-toolchain-compat.yml",
    "v10-wp6-identity-audit.yml",
)

CURRENT_CRITICAL_FOLLOWUP_RETRY_WORKFLOWS = (
    "v10-live-gateway-authority-contract.yml",
    "v10-wp16-web-design-system-audit.yml",
    "v10-wp17-application-shell-audit.yml",
    "v10-wp18-portfolio-dashboard-audit.yml",
    "v10-wp19-watchtower-incidents-audit.yml",
    "v10-wp20-research-dossier-audit.yml",
    "v10-wp21-decision-risk-plan-audit.yml",
    "v10-wp22-system-admin-audit.yml",
    "v10-wp22a-clientless-access-audit.yml",
    "v10-wp22a-phase2-product-auth-audit.yml",
    "v10-phase4-free-preview-deploy.yml",
)

HOSTED_ALIGNMENT_WORKFLOW = "v10-hosted-release-alignment.yml"

RETRY_MARKERS = (
    "bootstrap_succeeded=0",
    "for bootstrap_attempt in 1 2 3; do",
    "git config --local http.lowSpeedLimit 1000",
    "git config --local http.lowSpeedTime 60",
    "fetch_status=0",
    "|| fetch_status=$?",
    "git config --local --unset-all credential.helper 2>/dev/null || true",
    "rm -rf .git",
    'sleep "$((bootstrap_attempt * 5))"',
    'if [ "$bootstrap_succeeded" -ne 1 ]; then',
    'echo "Repository bootstrap transport failed after 3 attempts." >&2',
    "exit 70",
)

BASH_PRE_HEAD_CLEANUP = "if git rev-parse --verify HEAD >/dev/null 2>&1; then"
CMD_PRE_HEAD_CLEANUP = "git rev-parse --verify HEAD >nul 2>nul"


class V10CIActionDownloadResilienceTests(unittest.TestCase):
    def test_current_self_hosted_authority_plane_has_no_codeload_actions(self) -> None:
        failures: list[str] = []
        for name in CURRENT_SELF_HOSTED_AUTHORITY_WORKFLOWS:
            path = WORKFLOWS / name
            if not path.is_file():
                failures.append(f"missing workflow: {name}")
                continue
            text = path.read_text(encoding="utf-8")
            for forbidden in (
                "uses: actions/checkout@",
                "uses: actions/upload-artifact@",
            ):
                if forbidden in text:
                    failures.append(f"{name} still depends on {forbidden}")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_current_self_hosted_authority_plane_uses_exact_sha_read_only_bootstrap(
        self,
    ) -> None:
        failures: list[str] = []
        required = (
            "contents: read",
            "runs-on: [self-hosted, Windows, X64, omni-cio-ci]",
            "Expose installed Git Bash before repository bootstrap",
            "Get-Command git.exe -ErrorAction Stop",
            "Join-Path $root 'bin'",
            "Join-Path $bin 'bash.exe'",
            "$env:GITHUB_PATH",
            "-Encoding utf8 -Append",
            "GITHUB_TOKEN: ${{ github.token }}",
            'GIT_TERMINAL_PROMPT: "0"',
            'GCM_INTERACTIVE: "0"',
            "find . -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +",
            "git init .",
            'git remote add origin "https://github.com/${GITHUB_REPOSITORY}.git"',
            'git config --local credential.helper ""',
            "git config --local --add credential.helper '!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f'",
            "git config --local --unset-all credential.helper",
            "git checkout --detach",
            'test "$(git rev-parse HEAD)" = "$EXPECTED_HEAD"',
            'test -z "$(git config --local --get-all credential.helper || true)"',
        )
        for name in CURRENT_SELF_HOSTED_AUTHORITY_WORKFLOWS:
            path = WORKFLOWS / name
            if not path.is_file():
                failures.append(f"missing workflow: {name}")
                continue
            text = path.read_text(encoding="utf-8")
            for token in required:
                if token not in text:
                    failures.append(f"{name} missing bootstrap contract: {token}")
            if "${{ secrets" in text or "secrets." in text:
                failures.append(
                    f"{name} must not consume repository/environment secrets"
                )
            if "continue-on-error: true" in text:
                failures.append(f"{name} must not soften an authority job")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_blocker_dependency_closure_retries_only_repository_transport(self) -> None:
        failures: list[str] = []

        for name in BLOCKER_DEPENDENCY_CLOSED_RETRY_WORKFLOWS:
            text = (WORKFLOWS / name).read_text(encoding="utf-8")
            bootstrap_count = text.count("Bootstrap exact ")
            if bootstrap_count == 0:
                failures.append(f"{name} has no exact repository bootstrap step")
                continue

            for marker in RETRY_MARKERS:
                if text.count(marker) < bootstrap_count:
                    failures.append(
                        f"{name} missing bounded retry marker for every bootstrap: {marker}"
                    )

            retry_loop_count = text.count("for bootstrap_attempt in 1 2 3; do")
            if retry_loop_count != bootstrap_count:
                failures.append(
                    f"{name} retry loop count {retry_loop_count} != bootstrap count {bootstrap_count}"
                )

            reset_count = text.count("git reset --hard HEAD")
            safe_cleanup_count = text.count(BASH_PRE_HEAD_CLEANUP) + text.count(
                CMD_PRE_HEAD_CLEANUP
            )
            if safe_cleanup_count < reset_count:
                failures.append(
                    f"{name} has cleanup reset that is not guarded for missing HEAD"
                )

        self.assertEqual(failures, [], "\n".join(failures))

    def test_current_critical_followup_closure_retries_repository_bootstrap(self) -> None:
        failures: list[str] = []

        for name in CURRENT_CRITICAL_FOLLOWUP_RETRY_WORKFLOWS:
            path = WORKFLOWS / name
            if not path.is_file():
                failures.append(f"missing workflow: {name}")
                continue
            text = path.read_text(encoding="utf-8")

            for marker in RETRY_MARKERS:
                if marker not in text:
                    failures.append(f"{name} missing current retry contract: {marker}")

            if text.count("for bootstrap_attempt in 1 2 3; do") != 1:
                failures.append(f"{name} must have exactly one repository bootstrap retry loop")
            if text.count("exit 70") != 1:
                failures.append(f"{name} must fail closed once after bootstrap exhaustion")
            if "continue-on-error: true" in text:
                failures.append(f"{name} must not soften current critical verification")

            reset_count = text.count("git reset --hard HEAD")
            safe_cleanup_count = text.count(BASH_PRE_HEAD_CLEANUP) + text.count(
                CMD_PRE_HEAD_CLEANUP
            )
            if safe_cleanup_count < reset_count:
                failures.append(
                    f"{name} has cleanup reset that is not guarded for missing HEAD"
                )

        self.assertEqual(failures, [], "\n".join(failures))

    def test_hosted_alignment_retries_bootstrap_and_post_probe_reconfirmation(
        self,
    ) -> None:
        text = (WORKFLOWS / HOSTED_ALIGNMENT_WORKFLOW).read_text(encoding="utf-8")

        for marker in RETRY_MARKERS:
            self.assertIn(marker, text)
        self.assertEqual(text.count("for bootstrap_attempt in 1 2 3; do"), 1)

        reconfirm = text.split(
            "- name: Reconfirm current main before publishing runtime PASS", 1
        )[1].split("- name: Clean self-hosted alignment workspace", 1)[0]
        for marker in (
            "reconfirm_succeeded=0",
            "for reconfirm_attempt in 1 2 3; do",
            "git config --local http.lowSpeedLimit 1000",
            "git config --local http.lowSpeedTime 60",
            "fetch_status=0",
            "|| fetch_status=$?",
            "git config --local --unset-all credential.helper 2>/dev/null || true",
            'sleep "$((reconfirm_attempt * 5))"',
            'if [ "$reconfirm_succeeded" -ne 1 ]; then',
            'echo "Current-main reconfirm transport failed after 3 attempts; runtime PASS is withheld." >&2',
            "exit 71",
            "phase=post_probe",
            "cat hosted_alignment_pass.txt",
        ):
            self.assertIn(marker, reconfirm)

        self.assertNotIn("rm -rf .git", reconfirm)
        exhaustion_guard = reconfirm.index('if [ "$reconfirm_succeeded" -ne 1 ]; then')
        current_main_read = reconfirm.index(
            'current_main_sha="$(git rev-parse refs/remotes/origin/main)"'
        )
        publish_pass = reconfirm.index("cat hosted_alignment_pass.txt")
        self.assertLess(exhaustion_guard, current_main_read)
        self.assertLess(current_main_read, publish_pass)

        reset_count = text.count("git reset --hard HEAD")
        safe_cleanup_count = text.count(BASH_PRE_HEAD_CLEANUP) + text.count(
            CMD_PRE_HEAD_CLEANUP
        )
        self.assertGreaterEqual(safe_cleanup_count, reset_count)
        self.assertNotIn("continue-on-error: true", text)


if __name__ == "__main__":
    unittest.main()
