'use strict';

const assert = require('node:assert/strict');
const { newestSonarCheck, assertCleanSonar } = require('./require_clean_sonar.cjs');
const REF = 'a'.repeat(40);
const ZERO_NEW = '[0 New issues](https://example.invalid/new)';
const ZERO_ACCEPTED = '[0 Accepted issues](https://example.invalid/accepted)';

function cleanCheck(changes = {}) {
  return { id: 100, head_sha: REF, name: 'SonarCloud Code Analysis',
    app: { slug: 'sonarqubecloud' }, status: 'completed', conclusion: 'success',
    output: { annotations_count: 0, summary: ZERO_NEW + '\n' + ZERO_ACCEPTED }, ...changes };
}

function runTests() {
  let passed = 0;
  assert.equal(assertCleanSonar(cleanCheck(), [], REF), true);
  assert.equal(assertCleanSonar(cleanCheck(), [], REF), true);
  passed += 2;
  const invalidChecks = [null, cleanCheck({ head_sha: 'b'.repeat(40) }),
    cleanCheck({ app: { slug: 'github-actions' } }), cleanCheck({ name: 'different check' }),
    cleanCheck({ id: 0 }), cleanCheck({ status: 'in_progress' }),
    cleanCheck({ conclusion: 'failure' }), cleanCheck({ conclusion: 'neutral' }),
    cleanCheck({ output: { annotations_count: 12, summary: ZERO_NEW + ZERO_ACCEPTED } }),
    cleanCheck({ output: { annotations_count: '0', summary: ZERO_NEW + ZERO_ACCEPTED } }),
    cleanCheck({ output: { annotations_count: 0, summary: '[12 New issues](https://example.invalid/new)\n' + ZERO_ACCEPTED } }),
    cleanCheck({ output: { annotations_count: 0, summary: ZERO_NEW + '\n[1 Accepted issue](https://example.invalid/accepted)' } }),
    cleanCheck({ output: { annotations_count: 0, summary: ZERO_NEW + ZERO_NEW + ZERO_ACCEPTED } }),
    cleanCheck({ output: { annotations_count: 0, summary: 'Quality Gate passed' } }),
    cleanCheck({ output: { annotations_count: 0, summary: null } })];
  for (const check of invalidChecks) {
    assert.throws(() => assertCleanSonar(check, [], REF));
    passed++;
  }
  const check = cleanCheck();
  assert.throws(() => assertCleanSonar(check, [{ annotation_level: 'warning' }], REF));
  assert.throws(() => assertCleanSonar(check, null, REF));
  assert.throws(() => assertCleanSonar(check, [], 'not-a-sha'));
  passed += 3;
  const pending = cleanCheck({ id: 101, status: 'in_progress', conclusion: null });
  const selected = newestSonarCheck([pending, check, cleanCheck({ id: 500, head_sha: 'b'.repeat(40) })], REF);
  assert.equal(selected, pending);
  assert.throws(() => assertCleanSonar(selected, [], REF));
  assert.equal(newestSonarCheck([], REF), null);
  assert.throws(() => newestSonarCheck(null, REF));
  passed += 4;
  return passed;
}

if (require.main === module) console.log('SONAR_GATE_TESTS=' + runTests());
module.exports = { runTests };
