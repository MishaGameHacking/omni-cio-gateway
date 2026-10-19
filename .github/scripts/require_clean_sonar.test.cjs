'use strict';

const assert = require('node:assert/strict');
const { test } = require('node:test');
const { newestSonarCheck, assertCleanSonar } = require('./require_clean_sonar.cjs');
const REF = 'a'.repeat(40);
const OTHER_REF = 'b'.repeat(40);
const ZERO_NEW = '[0 New issues](https://example.invalid/new)';
const ZERO_ACCEPTED = '[0 Accepted issues](https://example.invalid/accepted)';

function cleanCheck(changes = {}) {
  return { id: 100, head_sha: REF, name: 'SonarCloud Code Analysis',
    app: { slug: 'sonarqubecloud' }, status: 'completed', conclusion: 'success',
    output: { annotations_count: 0, summary: ZERO_NEW + '\n' + ZERO_ACCEPTED }, ...changes };
}

function report(changes) {
  return cleanCheck({ output: { ...cleanCheck().output, ...changes } });
}

const cases = [
  ['accepts an exact-head zero-issue result', () => {
    assert.equal(assertCleanSonar(cleanCheck(), [], REF), true);
  }],
  ['repeated verification has no stateful-regex side effects', () => {
    const check = cleanCheck();
    for (let attempt = 0; attempt < 4; attempt++) {
      assert.equal(assertCleanSonar(check, [], REF), true);
    }
  }],
];

const invalidChecks = [
  ['missing check', null, 'sonar_exact_head_result_missing'],
  ['another commit', cleanCheck({ head_sha: OTHER_REF }), 'sonar_exact_head_result_missing'],
  ['another app', cleanCheck({ app: { slug: 'github-actions' } }), 'sonar_exact_head_result_missing'],
  ['missing app', cleanCheck({ app: null }), 'sonar_exact_head_result_missing'],
  ['another check name', cleanCheck({ name: 'different check' }), 'sonar_exact_head_result_missing'],
  ['zero check ID', cleanCheck({ id: 0 }), 'sonar_exact_head_result_missing'],
  ['unsafe check ID', cleanCheck({ id: Number.MAX_SAFE_INTEGER + 1 }), 'sonar_exact_head_result_missing'],
  ['pending analysis', cleanCheck({ status: 'in_progress' }), 'sonar_quality_gate_not_successful'],
  ['failed analysis', cleanCheck({ conclusion: 'failure' }), 'sonar_quality_gate_not_successful'],
  ['neutral analysis', cleanCheck({ conclusion: 'neutral' }), 'sonar_quality_gate_not_successful'],
  ['cancelled analysis', cleanCheck({ conclusion: 'cancelled' }), 'sonar_quality_gate_not_successful'],
  ['missing output', cleanCheck({ output: null }), 'sonar_annotations_not_clean_or_incomplete'],
  ['reported annotations', report({ annotations_count: 12 }), 'sonar_annotations_not_clean_or_incomplete'],
  ['string annotation count', report({ annotations_count: '0' }), 'sonar_annotations_not_clean_or_incomplete'],
  ['new issues', report({ summary: '[12 New issues](https://example.invalid/new)\n' + ZERO_ACCEPTED }), 'sonar_summary_zero_issues_not_confirmed'],
  ['accepted issue', report({ summary: ZERO_NEW + '\n[1 Accepted issue](https://example.invalid/accepted)' }), 'sonar_summary_zero_issues_not_confirmed'],
  ['duplicate new counts', report({ summary: ZERO_NEW + ZERO_NEW + ZERO_ACCEPTED }), 'sonar_summary_zero_issues_not_confirmed'],
  ['duplicate accepted counts', report({ summary: ZERO_NEW + ZERO_ACCEPTED + ZERO_ACCEPTED }), 'sonar_summary_zero_issues_not_confirmed'],
  ['contradictory counts', report({ summary: ZERO_NEW + ZERO_ACCEPTED + '[1 New issue](https://example.invalid/new)' }), 'sonar_summary_zero_issues_not_confirmed'],
  ['gate status without counts', report({ summary: 'Quality Gate passed' }), 'sonar_summary_zero_issues_not_confirmed'],
  ['null summary', report({ summary: null }), 'sonar_summary_schema_invalid'],
  ['oversized summary', report({ summary: 'x'.repeat(50_001) }), 'sonar_summary_schema_invalid'],
];
for (const [name, check, message] of invalidChecks) {
  cases.push(['rejects ' + name, () => {
    assert.throws(() => assertCleanSonar(check, [], REF), { message });
  }]);
}
for (const [name, annotations] of [['returned warning', [{ annotation_level: 'warning' }]], ['missing annotation list', null]]) {
  cases.push(['rejects ' + name, () => {
    const check = cleanCheck();
    assert.throws(() => assertCleanSonar(check, annotations, REF), {
      message: 'sonar_annotations_not_clean_or_incomplete',
    });
  }]);
}
for (const ref of ['not-a-sha', null, 'A'.repeat(40)]) {
  cases.push(['rejects malformed expected SHA: ' + String(ref), () => {
    const check = cleanCheck();
    assert.throws(() => assertCleanSonar(check, [], ref), { message: 'sonar_exact_head_result_missing' });
  }]);
}
for (const status of ['in_progress', 'completed']) {
  cases.push(['does not replace the newest ' + status + ' analysis with an older success', () => {
    const previous = cleanCheck();
    const newer = cleanCheck({ id: 101, status, conclusion: status === 'completed' ? 'failure' : null });
    const selected = newestSonarCheck([newer, previous, cleanCheck({ id: 500, head_sha: OTHER_REF })], REF);
    assert.equal(selected, newer);
    assert.throws(() => assertCleanSonar(selected, [], REF), { message: 'sonar_quality_gate_not_successful' });
  }]);
}
cases.push(['ignores unrelated and malformed checks while selecting the newest result', () => {
  const check = cleanCheck();
  const selected = newestSonarCheck([null, {}, cleanCheck({ id: 999, app: { slug: 'github-actions' } }), check], REF);
  assert.equal(selected, check);
}]);
cases.push(['returns no result for an empty check list', () => {
  assert.equal(newestSonarCheck([], REF), null);
}]);
cases.push(['rejects a missing check list', () => {
  assert.throws(() => newestSonarCheck(null, REF), { message: 'sonar_checks_schema_invalid' });
}]);

// Existing github-script callers run the same assertions synchronously. The
// CLI exposes each case to Node's real test runner rather than a manual counter.
function runTests() {
  for (const [, execute] of cases) execute();
  return cases.length;
}

if (require.main === module) {
  for (const [name, execute] of cases) test(name, execute);
}
module.exports = { runTests };
