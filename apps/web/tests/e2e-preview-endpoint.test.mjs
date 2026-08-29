import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { resolvePreviewEndpoint, resolvePreviewPort } from "../scripts/e2e-preview-endpoint.mjs";

const runE2eSource = fs.readFileSync(fileURLToPath(new URL("../scripts/run-e2e.mjs", import.meta.url)), "utf8");
const playwrightSource = fs.readFileSync(fileURLToPath(new URL("../playwright.config.ts", import.meta.url)), "utf8");

test("local browser evidence retains the canonical 4173 fallback", () => {
  assert.deepEqual(resolvePreviewEndpoint({}), {
    port: 4173,
    url: "http://127.0.0.1:4173/",
  });
});

test("explicit preview port override is validated and propagated", () => {
  assert.equal(resolvePreviewPort({ OMNI_WEB_PREVIEW_PORT: "43173" }), 43173);
  assert.throws(() => resolvePreviewPort({ OMNI_WEB_PREVIEW_PORT: "abc" }), /decimal digits/);
  assert.throws(() => resolvePreviewPort({ OMNI_WEB_PREVIEW_PORT: "80" }), /1024 through 65535/);
  assert.throws(() => resolvePreviewPort({ OMNI_WEB_PREVIEW_PORT: "65536" }), /1024 through 65535/);
});

test("GitHub browser jobs receive deterministic run-scoped preview ports", () => {
  const wp17 = {
    GITHUB_RUN_ID: "33232822220",
    GITHUB_JOB: "wp17-application-shell",
    GITHUB_RUN_ATTEMPT: "1",
    RUNNER_NAME: "omni-cio-ci",
  };
  const wp20 = {
    GITHUB_RUN_ID: "33232822183",
    GITHUB_JOB: "wp20-research-dossier",
    GITHUB_RUN_ATTEMPT: "1",
    RUNNER_NAME: "omni-cio-ci-3",
  };

  const first = resolvePreviewPort(wp17);
  assert.equal(resolvePreviewPort(wp17), first);
  assert.notEqual(resolvePreviewPort(wp20), first);
  assert.ok(first >= 18000 && first < 44000);
  assert.ok(resolvePreviewPort(wp20) >= 18000 && resolvePreviewPort(wp20) < 44000);
});

test("malformed GitHub identity fails closed instead of silently sharing a port", () => {
  assert.throws(() => resolvePreviewPort({ GITHUB_RUN_ID: "run-1" }), /GITHUB_RUN_ID/);
  assert.throws(
    () => resolvePreviewPort({ GITHUB_RUN_ID: "1", GITHUB_RUN_ATTEMPT: "0" }),
    /at least 1/,
  );
});

test("browser harness propagates the isolated endpoint into Playwright", () => {
  assert.match(runE2eSource, /String\(previewPort\)/);
  assert.match(runE2eSource, /OMNI_WEB_PREVIEW_URL: previewUrl/);
  assert.doesNotMatch(runE2eSource, /"--port",\s*"4173"/);
  assert.match(playwrightSource, /process\.env\.OMNI_WEB_PREVIEW_URL/);
  assert.match(playwrightSource, /baseURL,/);
});
