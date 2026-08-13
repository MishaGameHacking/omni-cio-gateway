import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

interface IncidentFixture { lifecycle_state: "ACTIVE" | "RESOLVED"; critical: boolean; alert_metadata_state: string; dedup: { reopened: boolean }; timeline: Array<{ state: string }>; evidence: Array<{ content_available: boolean; watchtower_alert_verified: boolean }> }
interface PayloadFixture { state: string; counts: { total: number; active: number; resolved: number; critical: number; reopened: number; missing_alert_metadata: number }; incidents: IncidentFixture[] }
const fixtures = JSON.parse(readFileSync(new URL("./fixtures/wp19_watchtower_incidents.golden.json", import.meta.url), "utf8")) as Record<"normal" | "missingEvidence", PayloadFixture>;

test("WP19 golden incident lifecycle exposes active resolved critical and reopened state", () => {
  const normal = fixtures.normal;
  assert.equal(normal.state, "READY");
  assert.equal(normal.counts.total, 2);
  assert.equal(normal.incidents.filter((item) => item.lifecycle_state === "ACTIVE").length, normal.counts.active);
  assert.equal(normal.incidents.filter((item) => item.lifecycle_state === "RESOLVED").length, normal.counts.resolved);
  assert.equal(normal.incidents.filter((item) => item.critical).length, normal.counts.critical);
  const reopened = normal.incidents.find((item) => item.dedup.reopened);
  assert.ok(reopened);
  assert.deepEqual(reopened.timeline.map((row) => row.state), ["open", "closed", "open"]);
});

test("WP19 missing evidence remains explicit and does not become a fabricated clean alert", () => {
  const partial = fixtures.missingEvidence;
  assert.equal(partial.state, "PARTIAL");
  assert.equal(partial.counts.missing_alert_metadata, 1);
  const incident = partial.incidents[0];
  assert.ok(incident);
  assert.equal(incident.alert_metadata_state, "MISSING");
  assert.equal(incident.evidence[0]?.content_available, false);
  assert.equal(incident.evidence[0]?.watchtower_alert_verified, false);
});

test("WP19 golden fixtures contain no credential or raw portfolio payload surface", () => {
  const encoded = JSON.stringify(fixtures);
  assert.doesNotMatch(encoded, /secret_ref|account_fingerprint|broker_token|provider_account_id|private_portfolio_payload/i);
});
