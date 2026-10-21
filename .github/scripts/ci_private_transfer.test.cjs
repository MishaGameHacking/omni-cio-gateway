const {test} = require('node:test');
const assert = require('node:assert/strict');
const transfer = require('./ci_private_transfer.cjs');

function fixture(options = {}) {
  const context = {eventName: 'push', sha: 'a'.repeat(40), runId: 42,
    repo: {owner: 'test', repo: 'repo'}, payload: {repository: {full_name: 'test/repo'}}};
  const env = {GITHUB_RUN_ATTEMPT: '1', CI_TRANSFER_KIND: 'probe'};
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
  await transfer({...f, command: 'probe'});
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
  await assert.rejects(transfer({...f, command: 'probe'}), /404 without authentication/);
  assert.equal(f.writes.includes('upload'), false);
});

test('tampered readback cannot produce a verified output', async () => {
  const f = fixture({corrupt: true});
  await assert.rejects(transfer({...f, command: 'probe'}), /digest or size mismatch/);
  assert.equal(f.writes.some(value => Array.isArray(value) && value[0] === 'archive_sha256'), false);
  await transfer({...f, command: 'cleanup'});
});

test('ownership rejects published, changed or unrelated releases', () => {
  const f = fixture();
  const release = {id: 7, draft: true, prerelease: true, published_at: null,
    tag_name: f.id.tag, target_commitish: f.id.head, body: f.id.body, assets: []};
  for (const change of [{draft: false}, {target_commitish: 'b'.repeat(40)}, {body: 'different'},
    {assets: [{name: 'unrelated'}]}, {published_at: '2026-10-21'}]) {
    assert.throws(() => transfer.owned({...release, ...change}, f.id), /ownership, privacy or contents/);
  }
});

test('an existing orphan tag is never deleted or reused', async () => {
  const f = fixture({orphan: true});
  await assert.rejects(transfer({...f, command: 'probe'}), /existing CI transfer tag/);
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
    pull_request: {head: {repo: {full_name: 'test/repo'}}}}};
  assert.equal(transfer.identity(context, f.env).head, f.context.sha);
  context.payload.pull_request.head.repo.full_name = 'foreign/repo';
  assert.throws(() => transfer.identity(context, f.env), /same-repository/);
});
