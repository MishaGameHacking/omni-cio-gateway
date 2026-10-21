'use strict';

// Keep the existing branch rule's required context backed by actual CI results.
// This script never creates statuses, changes protection, or supplies bypasses.
const { newestSonarCheck, assertCleanSonar } = require('./require_clean_sonar.cjs');
const BACKEND_PATH = '.github/workflows/backend-ci.yml';
const BACKEND_JOB = 'Backend smoke test';

function sourceIdentity(context) {
  const repository = context.repo.owner + '/' + context.repo.repo;
  const pull = context.payload.pull_request;
  const isPull = context.eventName === 'pull_request';
  if (isPull && (pull?.base?.ref !== 'main' || pull?.head?.repo?.full_name !== repository)) {
    throw new Error('merge_gate_untrusted_pull_request');
  }
  if (!isPull && (!['push', 'workflow_dispatch'].includes(context.eventName) || context.ref !== 'refs/heads/main')) {
    throw new Error('merge_gate_unsupported_event');
  }
  const identity = { repository, head: isPull ? pull.head.sha : context.sha,
    base: isPull ? pull.base.sha : null, number: isPull ? pull.number : null,
    event: isPull ? 'pull_request' : 'push' };
  if (![identity.head, ...(isPull ? [identity.base] : [])].every(value => typeof value === 'string' && /^[a-f0-9]{40}$/.test(value))) {
    throw new Error('merge_gate_invalid_source');
  }
  return identity;
}

function newestBackendRun(runs, identity) {
  if (!Array.isArray(runs)) throw new Error('merge_gate_invalid_runs');
  const candidates = runs.filter(run => run.head_sha === identity.head && run.path === BACKEND_PATH &&
    run.event === identity.event && run.repository?.full_name === identity.repository &&
    run.head_repository?.full_name === identity.repository);
  if (candidates.some(run => !Number.isSafeInteger(run.id) || run.id <= 0)) throw new Error('merge_gate_invalid_run_id');
  return candidates.reduce((newest, run) => !newest || run.id > newest.id ? run : newest, null);
}

function assertBackend(run, jobs) {
  if (run.status !== 'completed' || run.conclusion !== 'success') throw new Error('merge_gate_backend_not_successful');
  if (!Number.isSafeInteger(run.run_attempt) || run.run_attempt < 1) throw new Error('merge_gate_invalid_run_attempt');
  if (!Array.isArray(jobs)) throw new Error('merge_gate_invalid_jobs');
  const matching = jobs.filter(job => job.name === BACKEND_JOB && job.run_id === run.id);
  if (matching.length !== 1 || matching[0].status !== 'completed' || matching[0].conclusion !== 'success') {
    throw new Error('merge_gate_backend_job_not_successful');
  }
}

async function assertCurrentSource(github, context, identity) {
  if (identity.number !== null) {
    const { data: pull } = await github.rest.pulls.get({ ...context.repo, pull_number: identity.number });
    if (pull.state !== 'open' || pull.head?.sha !== identity.head || pull.base?.sha !== identity.base ||
        pull.base?.ref !== 'main' || pull.head?.repo?.full_name !== identity.repository) {
      throw new Error('merge_gate_pull_source_changed');
    }
  } else {
    const { data: ref } = await github.rest.git.getRef({ ...context.repo, ref: 'heads/main' });
    if (ref.object?.sha !== identity.head) throw new Error('merge_gate_main_changed');
  }
}

async function readBackend(github, context, identity) {
  const { data } = await github.rest.actions.listWorkflowRuns({ ...context.repo,
    workflow_id: 'backend-ci.yml', head_sha: identity.head, event: identity.event, per_page: 100 });
  if (!Number.isSafeInteger(data.total_count) || data.total_count < 0 || data.total_count > 100 ||
      data.workflow_runs?.length !== data.total_count) throw new Error('merge_gate_backend_inventory_incomplete');
  return newestBackendRun(data.workflow_runs, identity);
}

async function waitForBackend(github, context, identity, sleep) {
  for (let attempt = 0; attempt < 60; attempt++) {
    const backend = await readBackend(github, context, identity);
    if (backend?.status === 'completed') return backend;
    if (attempt < 59) await sleep(10000);
  }
  throw new Error('merge_gate_backend_not_ready');
}

async function verify({ github, context, core, androidResult, sleep = ms => new Promise(resolve => setTimeout(resolve, ms)) }) {
  if (androidResult !== 'success') throw new Error('merge_gate_android_not_successful');
  const identity = sourceIdentity(context);
  await assertCurrentSource(github, context, identity);
  const backend = await waitForBackend(github, context, identity, sleep);
  const jobs = await github.paginate(github.rest.actions.listJobsForWorkflowRun,
    { ...context.repo, run_id: backend.id, filter: 'latest', per_page: 100 });
  assertBackend(backend, jobs);
  const checks = await github.paginate(github.rest.checks.listForRef,
    { ...context.repo, ref: identity.head, check_name: 'SonarCloud Code Analysis', per_page: 100 });
  const sonar = newestSonarCheck(checks, identity.head);
  if (!sonar) throw new Error('merge_gate_sonar_missing');
  const annotations = await github.paginate(github.rest.checks.listAnnotations,
    { ...context.repo, check_run_id: sonar.id, per_page: 100 });
  assertCleanSonar(sonar, annotations, identity.head);
  // A rerun or push during verification must not leave an obsolete success.
  const current = await readBackend(github, context, identity);
  if (current?.id !== backend.id || current?.run_attempt !== backend.run_attempt ||
      current?.status !== 'completed' || current?.conclusion !== 'success') throw new Error('merge_gate_backend_changed');
  await assertCurrentSource(github, context, identity);
  core.info('AUTHORITATIVE_MERGE_GATE=' + JSON.stringify({ head: identity.head, base: identity.base,
    android_run: context.runId, backend_run: backend.id, backend_attempt: backend.run_attempt, sonar_check: sonar.id }));
}

module.exports = { verify, sourceIdentity, newestBackendRun, assertBackend };
