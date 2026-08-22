from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = "https://api.github.com"
EXPECTED_MAIN_SHA = os.environ["EXPECTED_MAIN_SHA"]
PREVIEW_ROOT = os.environ["PREVIEW_ROOT"].rstrip("/") + "/"
RESULT_REPO_PATH = os.environ["RESULT_REPO_PATH"]
RESULT_BRANCH = os.environ["RESULT_BRANCH"]
REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]


def _headers(*, json_body: bool = False) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "omni-cio-v10-temp-phase4-status",
    }
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _github_json(path: str, *, method: str = "GET", body: object | None = None) -> object:
    data = None
    if body is not None:
        data = json.dumps(body, separators=(",", ":")).encode("utf-8")
    request = Request(
        f"{API}/repos/{REPO}{path}",
        data=data,
        headers=_headers(json_body=body is not None),
        method=method,
    )
    with urlopen(request, timeout=45) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def _safe(value: object) -> str:
    return str(value if value is not None else "").replace("\r", " ").replace("\n", " ").replace("=", " ").replace("|", " ").strip()


def _emit_workflow(lines: list[str], workflow: str, prefix: str, required_event: str | None) -> None:
    try:
        payload = _github_json(f"/actions/workflows/{workflow}/runs?per_page=40")
        assert isinstance(payload, dict)
        rows = payload.get("workflow_runs", [])
        matches = [
            row
            for row in rows
            if isinstance(row, dict)
            and row.get("head_sha") == EXPECTED_MAIN_SHA
            and row.get("head_branch") == "main"
            and (required_event is None or row.get("event") == required_event)
        ]
        matches.sort(key=lambda row: int(row.get("run_number", 0)), reverse=True)
        lines.append(f"{prefix}_MATCH_COUNT={len(matches)}")
        if not matches:
            lines.append(f"{prefix}_RUN_FOUND=false")
            return
        run = matches[0]
        lines.extend(
            [
                f"{prefix}_RUN_FOUND=true",
                f"{prefix}_RUN_ID={_safe(run.get('id'))}",
                f"{prefix}_RUN_NUMBER={_safe(run.get('run_number'))}",
                f"{prefix}_EVENT={_safe(run.get('event'))}",
                f"{prefix}_STATUS={_safe(run.get('status'))}",
                f"{prefix}_CONCLUSION={_safe(run.get('conclusion'))}",
                f"{prefix}_HEAD_SHA={_safe(run.get('head_sha'))}",
                f"{prefix}_CREATED_AT={_safe(run.get('created_at'))}",
                f"{prefix}_UPDATED_AT={_safe(run.get('updated_at'))}",
            ]
        )
        jobs_url = str(run.get("jobs_url", ""))
        marker = f"{API}/repos/{REPO}"
        if not jobs_url.startswith(marker):
            lines.append(f"{prefix}_JOBS_URL_INVALID=true")
            return
        jobs_payload = _github_json(jobs_url[len(marker):])
        assert isinstance(jobs_payload, dict)
        for job in jobs_payload.get("jobs", []):
            if not isinstance(job, dict):
                continue
            lines.append(
                f"{prefix}_JOB={_safe(job.get('name'))}|status={_safe(job.get('status'))}|conclusion={_safe(job.get('conclusion'))}|id={_safe(job.get('id'))}"
            )
    except Exception as exc:
        lines.append(f"{prefix}_METADATA_ERROR={_safe(type(exc).__name__ + ': ' + str(exc))}")


def _probe(lines: list[str], url: str, prefix: str, *, parse_health: bool) -> None:
    request = Request(url, headers={"Accept": "application/json,text/html;q=0.9,*/*;q=0.8", "User-Agent": "omni-cio-v10-temp-phase4-status"}, method="GET")
    try:
        with urlopen(request, timeout=45) as response:
            status = int(response.status)
            raw = response.read()
            headers = {key.lower(): value for key, value in response.headers.items()}
        lines.append(f"{prefix}_HTTP_STATUS={status}")
        for header in (
            "cache-control",
            "strict-transport-security",
            "x-content-type-options",
            "content-security-policy",
            "referrer-policy",
            "permissions-policy",
            "x-frame-options",
        ):
            lines.append(f"{prefix}_HEADER_{header.replace('-', '_').upper()}={_safe(headers.get(header, ''))}")
        text = raw.decode("utf-8", errors="replace")
        if parse_health:
            payload = json.loads(text)
            if isinstance(payload, dict):
                lines.extend(
                    [
                        f"HEALTH_STATUS={_safe(payload.get('status'))}",
                        f"HEALTH_RELEASE_SHA={_safe(payload.get('release_sha'))}",
                        f"HEALTH_DATABASE={_safe(payload.get('database'))}",
                        f"HEALTH_SYNTHETIC_PREVIEW={_safe(payload.get('synthetic_preview'))}",
                    ]
                )
        else:
            lowered = text.lower()
            start = lowered.find("<title>")
            end = lowered.find("</title>", start + 7) if start >= 0 else -1
            title = text[start + 7:end] if start >= 0 and end > start else ""
            lines.append(f"ROOT_TITLE={_safe(title)}")
    except HTTPError as exc:
        lines.append(f"{prefix}_HTTP_STATUS={int(exc.code)}")
        lines.append(f"{prefix}_ERROR=HTTPError {_safe(exc.reason)}")
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        lines.append(f"{prefix}_ERROR={_safe(type(exc).__name__ + ': ' + str(exc))}")


def _publish(lines: list[str]) -> None:
    result = "\n".join(lines) + "\n"
    encoded = base64.b64encode(result.encode("utf-8")).decode("ascii")
    content_path = "/contents/" + RESULT_REPO_PATH
    existing_sha: str | None = None
    try:
        existing = _github_json(content_path + "?ref=" + RESULT_BRANCH.replace("/", "%2F"))
        if isinstance(existing, dict) and isinstance(existing.get("sha"), str):
            existing_sha = existing["sha"]
    except HTTPError as exc:
        if int(exc.code) != 404:
            raise
    body: dict[str, object] = {
        "message": "Publish sanitized exact-main deploy diagnostic",
        "content": encoded,
        "branch": RESULT_BRANCH,
    }
    if existing_sha:
        body["sha"] = existing_sha
    _github_json(content_path, method="PUT", body=body)
    print(result, end="")
    print(f"SANITIZED_RESULT_PUBLISHED path={RESULT_REPO_PATH}")


def main() -> int:
    lines = [
        "DIAGNOSTIC_TIMESTAMP_UTC=" + datetime.now(timezone.utc).isoformat(),
        "EXPECTED_MAIN_SHA=" + EXPECTED_MAIN_SHA,
        "PUBLIC_URL=" + PREVIEW_ROOT,
    ]
    _emit_workflow(lines, "regression-shield.yml", "REGRESSION", "push")
    _emit_workflow(lines, "v10-phase4-free-preview-deploy.yml", "DEPLOY", None)
    _probe(lines, PREVIEW_ROOT, "ROOT", parse_health=False)
    _probe(lines, PREVIEW_ROOT + "healthz", "HEALTH", parse_health=True)
    _publish(lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
