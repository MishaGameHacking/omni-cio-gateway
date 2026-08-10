import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { isOperationalState, operationalStates, viewportMatrix } from "../src/design-system/contracts";

test("canonical operational vocabulary is represented exactly", () => {
  assert.deepEqual(operationalStates, ["READY", "PARTIAL", "STALE", "DEGRADED", "BLOCKED", "ERROR", "OFFLINE", "RECOVERING", "OWNER_ACTION_REQUIRED"]);
  assert.equal(isOperationalState("STALE"), true);
  assert.equal(isOperationalState("UNKNOWN"), false);
});

test("required responsive matrix is explicit", () => {
  assert.deepEqual(viewportMatrix, [360, 768, 1440]);
});

test("theme, risk and reduced-motion tokens are source controlled", () => {
  const css = fs.readFileSync(path.resolve("src/design-system/tokens.css"), "utf8") + fs.readFileSync(path.resolve("src/design-system/base.css"), "utf8");
  for (const token of ["[data-theme=\"dark\"]", "--risk-critical", "--warning-bg", "--error-bg", "prefers-reduced-motion", "focus-visible"]) assert.match(css, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
});
