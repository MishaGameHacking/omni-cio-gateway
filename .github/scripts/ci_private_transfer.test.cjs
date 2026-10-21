const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const transfer = require('./ci_private_transfer.cjs');

function fixture(options = {}) {
  const context = {eventName: 'push', sha: 'a'.repeat(40), runId: 42,
    repo: {owner: 'test', repo: 'repo'}, payload: {repository: {full_name: 'test/repo'}}};
  const env = {GITHUB_RUN_ATTEMPT: '1'};
  const id = transfer.identity(context, env);
  const writes = [];
  let release = null;
  let bytes;
  const missing = () => {const error = new Error('missing'); error.status = 404; throw error;};
  const github = {paginate: async () => release ? [release] : [], rest: {
    git: {getRef: async () => options.orphan ? {data: {object: {type: 'commit', sha: context.sha}}} : missing(),
      deleteRef: async () => writes.push('delete-tag')},
    repos: {
      listReleases() {},
      createRelease: async value => {
        writes.push(['create', value]);
        release = {id: 7, assets: [], published_at: null, ...value};
        return {data: release};
      },
      uploadReleaseAsset: async value => {
        writes.push('upload'); bytes = Buffer.from(value.data);
        const asset = {id: 8, name: value.name, state: 'uploaded', size: bytes.length};
        release.assets.push(asset);
        return {data: asset};
      },
      deleteReleaseAsset: async () => {writes.push('delete-probe'); release.assets = [];},
      getReleaseAsset: async () => ({data: options.corrupt ? Buffer.from('tampered') : bytes}),
      getRelease: async () => release ? {data: release} : missing(),
      deleteRelease: async () => {writes.push('delete'); release = null;},
    },
  }};
  const anonymousFetch = async (_url, request) => {
    assert.equal(request.headers.authorization, undefined);
    assert.equal(request.redirect, 'manual');
    return {status: options.public ? 200 : 404};
  };
  const core = {info: value => writes.push(value), setOutput: (name, value) => writes.push([name, value])};
  return {github, context, core, env, anonymousFetch, writes, id};
}

test('synthetic handoff verifies private readback then deletes only its draft', async () => {
  const f = fixture();
  await transfer({...f, command: 'prepare'});
  const creation = f.writes.find(value => Array.isArray(value) && value[0] === 'create')[1];
  assert.equal(creation.draft, true);
  assert.equal(creation.make_latest, 'false');
  assert.equal(creation.target_commitish, f.context.sha);
  await transfer({...f, command: 'cleanup'});
  assert.equal(f.writes.at(-1), 'CI_PRIVATE_TRANSFER_CLEANUP=verified_absent');
  assert.equal(f.writes.filter(value => value === 'delete').length, 1);
});

test('anonymous availability blocks any file upload', async () => {
  const f = fixture({public: true});
  await assert.rejects(transfer({...f, command: 'prepare'}), /404 without authentication/);
  assert.equal(f.writes.includes('upload'), false);
});

test('tampered readback cannot produce a verified output', async () => {
  const f = fixture({corrupt: true});
  await assert.rejects(transfer({...f, command: 'prepare'}), /digest or size mismatch/);
  assert.equal(f.writes.some(value => Array.isArray(value) && value[0] === 'archive_sha256'), false);
  await transfer({...f, command: 'cleanup'});
});

test('ownership rejects published, changed or unrelated releases', () => {
  const f = fixture();
  const release = {id: 7, draft: true, prerelease: true, published_at: null,
    tag_name: f.id.tag, target_commitish: f.id.target, body: f.id.body, assets: []};
  for (const change of [{draft: false}, {target_commitish: 'b'.repeat(40)}, {body: 'different'},
    {assets: [{name: 'unrelated'}]}, {published_at: '2026-10-21'}]) {
    assert.throws(() => transfer.owned({...release, ...change}, f.id), /ownership, privacy or contents/);
  }
});

test('an existing orphan tag is never deleted or reused', async () => {
  const f = fixture({orphan: true});
  await assert.rejects(transfer({...f, command: 'prepare'}), /existing CI transfer tag/);
  await assert.rejects(transfer({...f, command: 'cleanup'}), /orphan tag/);
  assert.deepEqual(f.writes, []);
});

test('foreign repository and unsupported identities fail before API calls', () => {
  const f = fixture();
  for (const change of [{eventName: 'pull_request'}, {sha: 'branch-name'},
    {payload: {repository: {full_name: 'foreign/repo'}}}]) {
    assert.throws(() => transfer.identity({...f.context, ...change}, f.env), /same-repository/);
  }
});

test('same-repository PR uses the tested merge identity while a fork is refused', () => {
  const f = fixture();
  const context = {...f.context, eventName: 'pull_request', payload: {...f.context.payload,
    pull_request: {head: {sha: 'b'.repeat(40), repo: {full_name: 'test/repo'}}}}};
  assert.equal(transfer.identity(context, f.env).head, f.context.sha);
  assert.equal(transfer.identity(context, f.env).target, 'b'.repeat(40));
  context.payload.pull_request.head.repo.full_name = 'foreign/repo';
  assert.throws(() => transfer.identity(context, f.env), /same-repository/);
});

test('upload reuses the prepared draft and never creates another release after build', async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'ci-handoff-test-'));
  try {
    fs.writeFileSync(path.join(folder, 'ci-handoff.zip'), 'synthetic signed input archive');
    const f = fixture();
    f.env.RUNNER_TEMP = folder;
    await transfer({...f, command: 'prepare'});
    f.github.rest.repos.createRelease = async () => {throw new Error('A later release creation is forbidden');};
    await transfer({...f, command: 'upload'});
    assert.equal(f.writes.filter(value => Array.isArray(value) && value[0] === 'create').length, 1);
    await transfer({...f, command: 'cleanup'});
    const unprepared = fixture();
    unprepared.env.RUNNER_TEMP = folder;
    await assert.rejects(transfer({...unprepared, command: 'upload'}), /preflight-owned CI draft/);
    assert.deepEqual(unprepared.writes, []);
  } finally {
    fs.rmSync(folder, {recursive: true, force: true});
  }
});


test('manual handoff is limited to main and keeps the exact tested commit', () => {
  const f = fixture();
  const context = {...f.context, eventName: 'workflow_dispatch', ref: 'refs/heads/main'};
  assert.equal(transfer.identity(context, f.env).head, f.context.sha);
  context.ref = 'refs/heads/feature';
  assert.throws(() => transfer.identity(context, f.env), /same-repository/);
});
