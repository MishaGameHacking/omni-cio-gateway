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

function isThemeScopedSelector(selector: string): boolean {
  return /\[data-theme=/.test(selector) || /^\s*@media\s*\(\s*prefers-color-scheme/.test(selector);
}

/**
 * Strips CSS comments and walks brace nesting so each custom-property
 * declaration/reference can be attributed to the selector block(s) it is
 * physically inside of. This lets the guard tell apart a token defined only
 * under a theme scope (e.g. `[data-theme="dark"]`) from one defined for the
 * default/unscoped root, so a dark-only definition can never stand in for a
 * missing default-scope definition.
 */
function collectScopedDeclarations(source: string): { rootDefinitions: Set<string>; rootUsages: Map<string, number> } {
  const clean = source.replace(/\/\*[\s\S]*?\*\//g, "");
  const rootDefinitions = new Set<string>();
  const rootUsages = new Map<string, number>();

  let depth = 0;
  let themeScopeDepth: number | null = null;
  let selectorBuf = "";
  let i = 0;
  while (i < clean.length) {
    const ch = clean[i];
    if (ch === "{") {
      const selector = selectorBuf.trim();
      if (themeScopeDepth === null && isThemeScopedSelector(selector)) themeScopeDepth = depth;
      depth += 1;
      selectorBuf = "";
      i += 1;
      continue;
    }
    if (ch === "}") {
      depth = Math.max(0, depth - 1);
      if (themeScopeDepth !== null && depth < themeScopeDepth + 1) themeScopeDepth = null;
      selectorBuf = "";
      i += 1;
      continue;
    }
    if (ch === ";") {
      const declaration = selectorBuf;
      if (themeScopeDepth === null) {
        const defMatch = declaration.match(/(--[a-z0-9_-]+)\s*:/i);
        if (defMatch) rootDefinitions.add(defMatch[1]);
        for (const match of declaration.matchAll(/var\(\s*(--[a-z0-9_-]+)\s*(,)?/gi)) {
          if (match[2] !== ",") rootUsages.set(match[1], (rootUsages.get(match[1]) ?? 0) + 1);
        }
      }
      selectorBuf = "";
      i += 1;
      continue;
    }
    selectorBuf += ch;
    i += 1;
  }

  return { rootDefinitions, rootUsages };
}

test("every Web CSS custom-property reference has a definition or explicit fallback", () => {
  const files = collectCssFiles(path.resolve("src"));
  const rootDefinitions = new Set<string>();
  const perFileUsages = new Map<string, Map<string, number>>();

  for (const file of files) {
    const source = fs.readFileSync(file, "utf8");
    const scoped = collectScopedDeclarations(source);
    for (const token of scoped.rootDefinitions) rootDefinitions.add(token);
    perFileUsages.set(file, scoped.rootUsages);
  }

  const unresolved: string[] = [];
  for (const [file, usages] of perFileUsages) {
    for (const token of usages.keys()) {
      if (!rootDefinitions.has(token)) unresolved.push(`${path.relative(path.resolve("src"), file)}: ${token}`);
    }
  }

  assert.deepEqual(unresolved, []);
});
