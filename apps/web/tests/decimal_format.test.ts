import assert from "node:assert/strict";
import { test } from "node:test";
import { formatDecimal } from "../src/app-shell/decimal-format.ts";

test("WP18 Decimal formatter never passes large values through binary float", () => {
  assert.equal(
    formatDecimal("9007199254740993.125", 2),
    "9\u00a0007\u00a0199\u00a0254\u00a0740\u00a0993,13",
  );
});

test("WP18 Decimal formatter rounds nanos using decimal digits", () => {
  assert.equal(formatDecimal("0.000000019", 8), "0,00000002");
  assert.equal(formatDecimal("999.999", 2), "1\u00a0000");
  assert.equal(formatDecimal("-1.005", 2), "-1,01");
});

test("WP18 Decimal formatter preserves explicit unknown and invalid text", () => {
  assert.equal(formatDecimal(null), "—");
  assert.equal(formatDecimal(undefined), "—");
  assert.equal(formatDecimal(""), "—");
  assert.equal(formatDecimal("not-a-decimal"), "not-a-decimal");
});
