const {test} = require('node:test');
const assert = require('node:assert/strict');
const requireMainRelease = require('./require_main_release.cjs');

function fixture() {
  const sha = 'a'.repeat(40);
  const context = {eventName: 'push', ref: 'refs/heads/main', sha,
    repo: {owner: 'test', repo: 'repo'},
    payload: {repository: {full_name: 'test/repo'}, head_commit: {message: 'release [publish-apk]'}}};
  const sonar = {id: 4, name: 'SonarCloud Code Analysis', head_sha: sha,
    app: {slug: 'sonarqubecloud'}, status: 'completed', conclusion: 'success',
    output: {annotations_count: 0, summary: '[0 New issues](url) [0 Accepted issues](url)'}};
  const backend = {id: 9, head_sha: sha, name: 'Backend CI', event: 'push',
    path: '.github/workflows/backend-ci.yml', status: 'completed', conclusion: 'success'};
  const state = {checks: [sonar], runs: [backend], annotations: [], main: sha, reads: 0};
  const github = {rest: {checks: {listForRef() {}, listAnnotations() {}},
    actions: {listWorkflowRunsForRepo() {}},
    git: {getRef: async () => ({data: {object: {type: 'commit', sha: state.main}}})}}};
  github.paginate = async method => {
    state.reads++;
    if (method === github.rest.checks.listForRef) return state.checks;
    if (method === github.rest.checks.listAnnotations) return state.annotations;
    if (method === github.rest.actions.listWorkflowRunsForRepo) return state.runs;
    throw new Error('Unexpected API');
  };
  return {github, context, state, sonar, backend};
}

test('an explicit main release requires current zero-issue Sonar and successful backend', async () => {
  const f = fixture();
  assert.deepEqual(await requireMainRelease(f), {head: f.context.sha, sonar: 4, backend: 9});
  f.context.eventName = 'workflow_dispatch';
  assert.equal((await requireMainRelease(f)).head, f.context.sha);
});

test('PRs, foreign repositories, branches and ordinary pushes never authorize publication', async () => {
  for (const change of [{eventName: 'pull_request'}, {ref: 'refs/heads/feature'},
    {payload: {repository: {full_name: 'test/repo'}, head_commit: {message: 'ordinary merge'}}},
    {payload: {repository: {full_name: 'foreign/repo'}, head_commit: {message: '[publish-apk]'}}}]) {
    const f = fixture();
    Object.assign(f.context, change);
    await assert.rejects(requireMainRelease(f), /explicit request/);
    assert.equal(f.state.reads, 0);
  }
});

test('a stale main head cannot publish verified old bytes', async () => {
  const f = fixture();
  f.state.main = 'b'.repeat(40);
  await assert.rejects(requireMainRelease(f), /Main moved/);
});

test('a newer failed backend run supersedes an older green run', async () => {
  const f = fixture();
  f.state.runs.push({...f.backend, id: 10, conclusion: 'failure'});
  await assert.rejects(requireMainRelease(f), /Backend CI must pass/);
});

test('missing or wrong-head backend evidence is rejected', async () => {
  for (const runs of [[], [{id: 9, head_sha: 'b'.repeat(40), name: 'Backend CI',
    event: 'push', path: '.github/workflows/backend-ci.yml', status: 'completed', conclusion: 'success'}]]) {
    const f = fixture();
    f.state.runs = runs;
    await assert.rejects(requireMainRelease(f), /Backend CI must pass/);
  }
});

test('Sonar annotations and newer nonzero findings stop publication', async () => {
  const f = fixture();
  f.state.annotations = [{message: 'unresolved finding'}];
  await assert.rejects(requireMainRelease(f), /sonar_annotations/);
  f.state.annotations = [];
  f.state.checks.push({...f.sonar, id: 5,
    output: {annotations_count: 0, summary: '[1 New issue](url) [0 Accepted issues](url)'}});
  await assert.rejects(requireMainRelease(f), /sonar_summary_zero/);
});
