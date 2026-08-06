import assert from "node:assert/strict";
import test from "node:test";

import {
  TOOLCHAIN_SMOKE_LABEL,
  buildToolchainSmokeLabel,
} from "../src/smoke_contract.ts";

test("buildToolchainSmokeLabel normalizes the suffix deterministically", () => {
  assert.equal(
    buildToolchainSmokeLabel("  WP3 protected  "),
    `${TOOLCHAIN_SMOKE_LABEL} — WP3 protected`,
  );
});

test("buildToolchainSmokeLabel rejects an empty suffix", () => {
  assert.throws(
    () => buildToolchainSmokeLabel("   "),
    /TOOLCHAIN_SMOKE_SUFFIX_EMPTY/,
  );
});
