import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { isOperationalState, operationalStates, viewportMatrix } from "../src/design-system/contracts.ts";

function collectCssFiles(root: string): string[] {
  const files: string[] = [];
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const entryPath = path.join(root, entry.name);
    if (entry.isDirectory()) files.push(...collectCssFiles(entryPath));
    else if (entry.isFile() && entry.name.endsWith(".css")) files.push(entryPath);
  }
  return files;
}

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

test("every Web CSS custom-property reference has a default token or explicit fallback", () => {
  const files = collectCssFiles(path.resolve("src"));
  const tokensSource = fs.readFileSync(path.resolve("src/design-system/tokens.css"), "utf8");
  const rootBlock = tokensSource.match(/:root\s*\{([\s\S]*?)\}/)?.[1];
  assert.ok(rootBlock, "tokens.css must declare the canonical default :root token set");

  const defaultDefinitions = new Set<string>();
  for (const match of rootBlock.matchAll(/(--[a-z0-9_-]+)\s*:/gi)) defaultDefinitions.add(match[1]);

  const unresolved: string[] = [];
  for (const file of files) {
    const source = fs.readFileSync(file, "utf8");
    for (const match of source.matchAll(/var\(\s*(--[a-z0-9_-]+)\s*(,)?/gi)) {
      if (!defaultDefinitions.has(match[1]) && match[2] !== ",") unresolved.push(`${path.relative(path.resolve("src"), file)}: ${match[1]}`);
    }
  }

  assert.deepEqual(unresolved, []);
});
