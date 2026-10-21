'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { verify, sourceIdentity, newestBackendRun } = require('./authoritative_merge_gate.cjs');

function fixture() {
  const head = 'a'.repeat(40), base = 'b'.repeat(40), repository = 'test/repo';
  const pull = { number: 5, state: 'open', head: { sha: head, repo: { full_name: repository } },
    base: { sha: base, ref: 'main' } };
  const context = { repo: { owner: 'test', repo: 'repo' }, eventName: 'pull_request', runId: 20,
    payload: { pull_request: structuredClone(pull) } };
  const backend = { id: 10, run_attempt: 1, head_sha: head, path: '.github/workflows/backend-ci.yml',
    event: 'pull_request', repository: { full_name: repository }, head_repository: { full_name: repository },
    status: 'completed', conclusion: 'success' };
  const sonar = { id: 30, head_sha: head, name: 'SonarCloud Code Analysis', app: { slug: 'sonarqubecloud' },
    status: 'completed', conclusion: 'success', output: { annotations_count: 0,
      summary: '[0 New issues](url) [0 Accepted issues](url)' } };
  const state = { pull, runs: [backend], jobs: [{ name: 'Backend smoke test', run_id: 10,
    status: 'completed', conclusion: 'success' }], checks: [sonar], annotations: [], receipts: [],
    total: 1, reads: 0, sleeps: 0, mutate: () => {} };
  const github = { rest: { pulls: { get: async () => ({ data: state.pull }) },
    git: { getRef: async () => ({ data: { object: { sha: state.main ?? head } } }) },
    actions: { listWorkflowRuns: async () => {
      state.reads++; state.mutate(state.reads);
      return { data: { total_count: state.total, workflow_runs: structuredClone(state.runs) } };
    }, listJobsForWorkflowRun() {} }, checks: { listForRef() {}, listAnnotations() {} } },
    paginate: async method => {
      if (method === github.rest.actions.listJobsForWorkflowRun) return state.jobs;
      if (method === github.rest.checks.listForRef) return state.checks;
      if (method === github.rest.checks.listAnnotations) return state.annotations;
      throw new Error('unexpected API');
    } };
  return { github, context, state, backend, sonar, androidResult: 'success',
    core: { info: value => state.receipts.push(value) }, sleep: async () => { state.sleeps++; } };
}

test('required context succeeds only with actual current Android, backend job and clean Sonar', async () => {
  const f = fixture();
  await verify(f);
  assert.equal(f.state.receipts.length, 1);
  assert.match(f.state.receipts[0], /"backend_run":10/);
  assert.equal(f.state.reads, 2);
});

test('failed, cancelled, skipped or missing Android never reads another green check', async () => {
  for (const androidResult of ['failure', 'cancelled', 'skipped', undefined]) {
    const f = fixture(); f.androidResult = androidResult;
    await assert.rejects(verify(f), /android_not_successful/);
    assert.equal(f.state.reads, 0);
    assert.deepEqual(f.state.receipts, []);
  }
});

test('foreign PRs, unsupported events and malformed source identities fail closed', () => {
  for (const change of [f => { f.context.eventName = 'pull_request_target'; },
    f => { f.context.payload.pull_request.head.repo.full_name = 'other/repo'; },
    f => { f.context.payload.pull_request.base.ref = 'release'; },
    f => { f.context.payload.pull_request.head.sha = 'not-a-sha'; }]) {
    const f = fixture(); change(f);
    assert.throws(() => sourceIdentity(f.context), /merge_gate_/);
  }
});

test('another workflow, repository, event or head cannot supply backend success', () => {
  const f = fixture(), identity = sourceIdentity(f.context);
  for (const change of [{ path: '.github/workflows/fake.yml' }, { head_sha: 'c'.repeat(40) },
    { event: 'push' }, { repository: { full_name: 'other/repo' } },
    { head_repository: { full_name: 'other/repo' } }]) {
    assert.equal(newestBackendRun([{ ...f.backend, ...change }], identity), null);
  }
});

test('newest failed backend supersedes an older success', async () => {
  const f = fixture();
  f.state.runs.push({ ...f.backend, id: 11, conclusion: 'failure' });
  f.state.total = 2;
  await assert.rejects(verify(f), /backend_not_successful/);
});

test('workflow success cannot replace missing, skipped, failed or duplicate backend job', async () => {
  for (const change of [f => { f.state.jobs = []; },
    f => { f.state.jobs[0].conclusion = 'skipped'; },
    f => { f.state.jobs[0].conclusion = 'failure'; },
    f => { f.state.jobs[0].run_id = 9; },
    f => { f.state.jobs.push({ ...f.state.jobs[0] }); }]) {
    const f = fixture(); change(f);
    await assert.rejects(verify(f), /backend_job_not_successful/);
  }
});

test('missing or pending backend times out without a receipt, and complete inventory is mandatory', async () => {
  for (const status of ['missing', 'in_progress']) {
    const f = fixture();
    if (status === 'missing') { f.state.runs = []; f.state.total = 0; }
    else f.backend.status = status;
    await assert.rejects(verify(f), /backend_not_ready/);
    assert.equal(f.state.sleeps, 59);
    assert.deepEqual(f.state.receipts, []);
  }
  const f = fixture(); f.state.total = 101;
  await assert.rejects(verify(f), /inventory_incomplete/);
});

test('a changed PR head or base prevents stale evidence from authorizing merge', async () => {
  for (const field of ['head', 'base']) {
    const f = fixture(); f.state.pull[field].sha = 'c'.repeat(40);
    await assert.rejects(verify(f), /source_changed/);
  }
});

test('Sonar issues, annotations, wrong head or wrong publisher cannot authorize merge', async () => {
  for (const change of [f => { f.sonar.head_sha = 'c'.repeat(40); },
    f => { f.sonar.app.slug = 'github-actions'; },
    f => { f.sonar.output.summary = '[1 New issue](url) [0 Accepted issues](url)'; },
    f => { f.state.annotations.push({ annotation_level: 'warning' }); }]) {
    const f = fixture(); change(f);
    await assert.rejects(verify(f), /sonar_/);
    assert.deepEqual(f.state.receipts, []);
  }
});

test('a newer rerun, a failed rerun, or a push during verification invalidates success', async () => {
  for (const change of [f => { f.backend.run_attempt = 2; },
    f => { f.backend.status = 'in_progress'; },
    f => { f.backend.conclusion = 'failure'; },
    f => { f.state.runs.push({ ...f.backend, id: 11 }); },
    f => { f.state.pull.base.sha = 'c'.repeat(40); }]) {
    const f = fixture(); f.state.mutate = read => { if (read === 2) change(f); };
    await assert.rejects(verify(f), /merge_gate_/);
    assert.deepEqual(f.state.receipts, []);
  }
});

test('main push and explicit main audit use the current main head and its push backend', async () => {
  for (const eventName of ['push', 'workflow_dispatch']) {
    const f = fixture();
    Object.assign(f.context, { eventName, ref: 'refs/heads/main', sha: f.backend.head_sha });
    f.backend.event = 'push';
    await verify(f);
    f.state.main = 'c'.repeat(40);
    await assert.rejects(verify(f), /main_changed/);
  }
});
