const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const retain = require('../../private_apk_review.cjs');
const head = 'b'.repeat(40);
const merge = 'a'.repeat(40);
const base = 'c'.repeat(40);

function fixture(options = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'private-apk-test-'));
  const destination = path.join(root, 'app/build/outputs/apk/preview');
  fs.mkdirSync(destination, {recursive: true});
  const apk = Buffer.from('synthetic APK bytes for publisher unit test only');
  const report = {min_sdk: 37, target_sdk: 37, package: 'ru.omnicio.app.debug', version_code: 35,
    version_name: '0.11.0-preview', debuggable: false, test_only: false, signature_v2: true,
    certificate_sha256: 'bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1',
    device_install_test: 'passed_on_emulators_not_a_physical_phone', bytes: apk.length,
    sha256: crypto.createHash('sha256').update(apk).digest('hex'), ...options.report};
  fs.writeFileSync(path.join(destination, 'app-preview.apk'), apk);
  fs.writeFileSync(path.join(destination, 'apk-verification.json'), JSON.stringify(report));
  const writes = [];
  const assets = new Map();
  let nextId = 100;
  const release = {id: 2, assets: [], draft: true, html_url: 'https://github.com/test/repo/releases/2'};
  const listReleases = () => {};
  const listForRef = () => {};
  const listAnnotations = () => {};
  const listWorkflowRunsForRepo = () => {};
  const github = {rest: {repos: {
    listReleases,
    getCommit: async () => ({data: {commit: {message: options.noRequest ? 'fix' : 'fix [private-apk]'}}}),
    createRelease: async value => { writes.push(['create', value]); return {data: release}; },
    uploadReleaseAsset: async value => {
      writes.push(['asset', value]);
      const id = nextId++;
      assets.set(id, Buffer.from(value.data));
      return {data: {id, name: value.name, browser_download_url: 'https://github.com/test/repo/asset/' + id}};
    },
    getReleaseAsset: async value => ({data: options.corruptReadback ? Buffer.from('corrupt') : assets.get(value.asset_id)}),
    updateRelease: async value => { writes.push(['update', value]); return {data: release}; },
  }, checks: {listForRef, listAnnotations}, actions: {listWorkflowRunsForRepo},
  pulls: {get: async () => ({data: {state: 'open', head: {sha: options.stale ? 'd'.repeat(40) : head}, base: {sha: base}}})}},
  paginate: async route => {
    if (route === listForRef) {
      const check = {id: 7, head_sha: options.wrongHead ? base : head,
        name: 'SonarCloud Code Analysis', app: {slug: options.fakeApp ? 'github-actions' : 'sonarqubecloud'},
        status: 'completed', conclusion: options.sonar || 'success',
        output: {annotations_count: options.annotation ? 1 : 0,
          summary: `[${options.newIssues || 0} New issues](https://example.invalid/new)\n[${options.acceptedIssues || 0} Accepted issues](https://example.invalid/accepted)`}};
      return options.newerPending ? [check, {...check, id: 9, status: 'in_progress', conclusion: null}] : [check];
    }
    if (route === listAnnotations) return options.annotation ? [{annotation_level: 'warning'}] : [];
    if (route === listWorkflowRunsForRepo) return [{id: 8, name: 'Backend CI', status: 'completed', conclusion: options.backend || 'success'}];
    if (route === listReleases) return [];
    throw new Error('Unexpected API route');
  }};
  const context = {eventName: 'pull_request', repo: {owner: 'test', repo: 'repo'}, sha: merge, runId: 123,
    payload: {repository: {private: !options.public}, pull_request: {number: 880,
      head: {sha: head, repo: {full_name: 'test/repo'}}, base: {sha: base}}}};
  const core = {notice: () => {}, info: value => writes.push(['info', value]),
    summary: {addHeading() {return this;}, addRaw() {return this;}, async write() {}}};
  const anonymousFetch = async (_url, request) => {
    assert.equal(request.headers.authorization, undefined);
    return {status: options.publicDraft ? 200 : 404};
  };
  return {root, github, context, core, writes, report, apk, anonymousFetch};
}

async function run(options, check) {
  const f = fixture(options);
  const old = process.env.GITHUB_WORKSPACE;
  process.env.GITHUB_WORKSPACE = f.root;
  try { await check(f); }
  finally {
    if (old === undefined) delete process.env.GITHUB_WORKSPACE;
    else process.env.GITHUB_WORKSPACE = old;
    fs.rmSync(f.root, {recursive: true, force: true});
  }
}

test('verified bytes remain a draft after upload and independent read-back', async () => {
  await run({}, async f => {
    await retain(f);
    const changes = f.writes.filter(([kind]) => kind === 'create' || kind === 'update');
    assert.equal(changes.length, 2);
    for (const [, value] of changes) {
      assert.equal(value.draft, true);
      assert.equal(value.make_latest, 'false');
    }
    assert.equal(f.writes.filter(([kind]) => kind === 'asset').length, 2);
    assert.match(f.writes.at(-1)[1], /"timeweb_updated":false/);
    assert.match(f.writes.at(-1)[1], /"draft":true/);
  });
});
test('a normal commit never creates a private APK', async () => {
  await run({noRequest: true}, async f => { await retain(f); assert.deepEqual(f.writes, []); });
});
test('public source repository can retain only an inaccessible verified draft', async () => {
  await run({public: true}, async f => {
    await retain(f);
    assert.equal(f.writes.find(([kind]) => kind === 'create')[1].draft, true);
  });
  await run({public: true, noRequest: true}, async f => {
    await retain(f);
    assert.deepEqual(f.writes, []);
  });
  await run({public: true, publicDraft: true}, async f => {
    await assert.rejects(retain(f), /404 without authentication/);
    assert.equal(f.writes.some(([kind]) => kind === 'asset'), false);
  });
});
test('stale PR cannot attach bytes as a current verified candidate', async () => {
  await run({stale: true}, async f => {
    await assert.rejects(retain(f), /PR changed/);
    assert.deepEqual(f.writes, []);
  });
});
test('failed Sonar or backend prevents APK retention', async () => {
  for (const options of [{sonar: 'failure'}, {backend: 'failure'}]) {
    await run(options, async f => {
      await assert.rejects(retain(f), /sonar_quality_gate_not_successful|must pass/);
      assert.deepEqual(f.writes, []);
    });
  }
});
test('compile-only or wrong artifact reports never create an APK draft', async () => {
  for (const report of [{device_install_test: 'separate_required_check'}, {sha256: '0'.repeat(64)},
      {version_code: 34}, {bytes: 1}, {debuggable: true}, {test_only: true},
      {package: 'ru.omnicio.app'}, {certificate_sha256: 'wrong'}, {signature_v2: false}]) {
    await run({report}, async f => {
      await assert.rejects(retain(f), /exact verified 0.11.0/);
      assert.deepEqual(f.writes, []);
    });
  }
});
test('a corrupt GitHub upload cannot be reported as verified', async () => {
  await run({corruptReadback: true}, async f => {
    await assert.rejects(retain(f), /upload read-back/);
    assert.equal(f.writes.filter(([kind]) => kind === 'update').length, 0);
    assert.equal(f.writes.filter(([kind]) => kind === 'info').length, 0);
  });
});
test('missing evidence fails without a release write', async () => {
  await run({}, async f => {
    fs.unlinkSync(path.join(f.root, 'app/build/outputs/apk/preview/apk-verification.json'));
    await assert.rejects(retain(f), /ENOENT/);
    assert.deepEqual(f.writes, []);
  });
});

test('old, future-target and malformed platform reports cannot produce a current draft', async () => {
  for (const report of [{min_sdk: 35}, {min_sdk: 36}, {min_sdk: '37'}, {min_sdk: null},
      {target_sdk: 36}, {target_sdk: 38}, {target_sdk: '37'}, {target_sdk: null}]) {
    await run({report}, async f => {
      await assert.rejects(retain(f), /exact current Android platform/);
      assert.deepEqual(f.writes, []);
    });
  }
});
test('a similarly named check from another app or SHA cannot authorize retention', async () => {
  for (const options of [{fakeApp: true}, {wrongHead: true}]) {
    await run(options, async f => {
      await assert.rejects(retain(f), /sonar_exact_head_result_missing/);
      assert.deepEqual(f.writes, []);
    });
  }
});
test('successful gate with annotations or nonzero issue counts remains blocked', async () => {
  for (const options of [{annotation: true}, {newIssues: 1}, {acceptedIssues: 1}]) {
    await run(options, async f => {
      await assert.rejects(retain(f), /sonar_annotations_not_clean_or_incomplete|sonar_summary_zero_issues_not_confirmed/);
      assert.deepEqual(f.writes, []);
    });
  }
});
test('new pending analysis cannot reuse an older successful analysis', async () => {
  await run({newerPending: true}, async f => {
    await assert.rejects(retain(f), /sonar_quality_gate_not_successful/);
    assert.deepEqual(f.writes, []);
  });
});
