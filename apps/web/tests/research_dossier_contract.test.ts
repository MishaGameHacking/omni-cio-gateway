import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const page = readFileSync(new URL("../src/app-shell/research-dossier.tsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../src/app-shell/research-dossier-api.ts", import.meta.url), "utf8");
const shell = readFileSync(new URL("../src/app-shell/app-shell.tsx", import.meta.url), "utf8");
const backend = readFileSync(new URL("../../../omni_cio/web/research_dossier_v1.py", import.meta.url), "utf8");

test("WP20 replaces the Research placeholder inside the accepted application shell", () => {
  assert.match(shell, /path === ["']\/research["']/);
  assert.match(shell, /ResearchDossierPage/);
  assert.match(page, /WP20 · RESEARCH DOSSIER/);
});

test("WP20 source facts and AI inference use separate semantic authority regions", () => {
  assert.match(page, /data-authority="source-evidence"/);
  assert.match(page, /data-authority="ai-non-authoritative"/);
  assert.match(page, /SOURCE FACT/);
  assert.match(page, /AI \/ INFERENCE CHANNEL/);
  assert.match(page, /НЕ ИСТОЧНИК ФАКТА/);
  assert.match(backend, /AI_GENERATED_NON_AUTHORITATIVE/);
  assert.match(backend, /authoritative.*False/);
});

test("WP20 never renders external research text as active HTML", () => {
  assert.doesNotMatch(page, /dangerouslySetInnerHTML/);
  assert.doesNotMatch(page, /innerHTML\s*=/);
  assert.match(backend, /_safe_source_href/);
  assert.match(backend, /_SAFE_LINK_SCHEMES = \{"http", "https"\}/);
});

test("WP20 exposes provenance time freshness contradiction unknown and confidence context", () => {
  for (const marker of ["Источник", "Получено", "Опубликовано", "FRESH", "Противоречия", "coverage gaps", "confidence_state"]) {
    assert.ok(`${page}\n${backend}`.includes(marker), marker);
  }
});

test("WP20 same-origin API is session scoped and no-store", () => {
  assert.match(api, /\/api\/v10\/web\/research-dossiers/);
  assert.match(api, /credentials:\s*["']same-origin["']/);
  assert.match(api, /cache:\s*["']no-store["']/);
  assert.match(backend, /sessions\.resolve/);
  assert.match(backend, /tenant_id=scope\.tenant_id/);
  assert.match(backend, /Cache-Control.*no-store/);
});

test("WP20 runtime does not start Block G or add broker-write authority", () => {
  const combined = `${page}\n${api}\n${backend}`;
  assert.doesNotMatch(combined, /SearXNG|LangGraph|Ollama|Playwright|search_web|fetch_source/);
  assert.doesNotMatch(combined, /@app\.(post|put|patch|delete)\(/i);
  assert.doesNotMatch(combined, /submit_order|PostOrder|withdraw|transfer|broker_trading/i);
  assert.doesNotMatch(combined, /localStorage|sessionStorage/);
});
