'use strict';

const CHECK_NAME = 'SonarCloud Code Analysis';
const APP_SLUG = 'sonarqubecloud';
const NEW_ISSUES = /\[(\d+) New issues?\]\(/g;
const ACCEPTED_ISSUES = /\[(\d+) Accepted issues?\]\(/g;

function isSonarCheck(check, ref) {
  return check?.head_sha === ref && check.name === CHECK_NAME &&
    check.app?.slug === APP_SLUG && Number.isSafeInteger(check.id) && check.id > 0;
}

function newestSonarCheck(checks, ref) {
  if (!Array.isArray(checks)) throw new Error('sonar_checks_schema_invalid');
  let newest = null;
  for (const check of checks) {
    if (isSonarCheck(check, ref) && (newest === null || check.id > newest.id)) newest = check;
  }
  return newest;
}

function requireZeroSummaryCount(summary, pattern) {
  const counts = [...summary.matchAll(pattern)];
  // A changed/ambiguous report format must not be silently interpreted as zero.
  if (counts.length !== 1 || counts[0][1] !== '0') {
    throw new Error('sonar_summary_zero_issues_not_confirmed');
  }
}

function assertCleanSonar(check, annotations, ref) {
  if (typeof ref !== 'string' || !/^[a-f0-9]{40}$/.test(ref) || !isSonarCheck(check, ref)) {
    throw new Error('sonar_exact_head_result_missing');
  }
  if (check.status !== 'completed' || check.conclusion !== 'success') {
    throw new Error('sonar_quality_gate_not_successful');
  }
  if (!Array.isArray(annotations) || annotations.length !== 0 || check.output?.annotations_count !== 0) {
    throw new Error('sonar_annotations_not_clean_or_incomplete');
  }
  const summary = check.output.summary;
  if (typeof summary !== 'string' || summary.length > 50_000) {
    throw new Error('sonar_summary_schema_invalid');
  }
  requireZeroSummaryCount(summary, NEW_ISSUES);
  requireZeroSummaryCount(summary, ACCEPTED_ISSUES);
  return true;
}

module.exports = { newestSonarCheck, assertCleanSonar };
