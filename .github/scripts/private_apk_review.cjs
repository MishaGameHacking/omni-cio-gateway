/* Keep an explicitly requested, emulator-verified APK in a private GitHub draft.
 * Never publish the draft, move a channel, dispatch deployment, or contact Timeweb.
 */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {newestSonarCheck, assertCleanSonar} = require('./require_clean_sonar.cjs');
const {inaccessibleWithoutAuth} = require('./ci_private_transfer.cjs');

const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function readInside(root, relative, limit) {
  const file = path.join(root, relative);
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size <= 0 || stat.size > limit ||
      !fs.realpathSync(file).startsWith(root + path.sep)) {
    throw new Error('Unsafe or missing private APK evidence');
  }
  return fs.readFileSync(file);
}

function validateBytes(report, apk) {
  if (report.min_sdk !== 37 || report.target_sdk !== 37) {
    throw new Error('Private APK requires the exact current Android platform');
  }
  if (report.package !== 'ru.omnicio.app.debug' || report.version_code !== 35 ||
      report.version_name !== '0.11.0-preview' || report.debuggable !== false ||
      report.test_only !== false || report.signature_v2 !== true ||
      report.certificate_sha256 !== 'bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1' ||
      report.device_install_test !== 'passed_on_emulators_not_a_physical_phone' ||
      report.bytes !== apk.length || report.sha256 !== digest(apk)) {
    throw new Error('Private APK is not the exact verified 0.11.0 candidate');
  }
}

async function qualityChecks(github, context, head) {
  const checks = await github.paginate(github.rest.checks.listForRef,
    {...context.repo, ref: head, per_page: 100});
  const sonar = newestSonarCheck(checks, head);
  const annotations = sonar ? await github.paginate(github.rest.checks.listAnnotations,
    {...context.repo, check_run_id: sonar.id, per_page: 100}) : [];
  assertCleanSonar(sonar, annotations, head);
  const runs = await github.paginate(github.rest.actions.listWorkflowRunsForRepo,
    {...context.repo, head_sha: head, event: 'pull_request', per_page: 100});
  const backend = runs.filter(run => run.name === 'Backend CI')
    .sort((a, b) => b.id - a.id)[0];
  if (backend?.status !== 'completed' || backend.conclusion !== 'success') {
    throw new Error('Exact-head Backend CI must pass before retaining a device-test APK');
  }
  return {sonar: sonar.id, backend: backend.id};
}

async function retainAsset(github, repo, release, name, bytes, type) {
  let asset = release.assets.find(item => item.name === name);
  if (!asset) {
    asset = (await github.rest.repos.uploadReleaseAsset({...repo, release_id: release.id,
      name, data: bytes, headers: {'content-type': type, 'content-length': bytes.length}})).data;
  }
  const received = Buffer.from((await github.rest.repos.getReleaseAsset({...repo,
    asset_id: asset.id, headers: {accept: 'application/octet-stream'}})).data);
  if (received.length !== bytes.length || digest(received) !== digest(bytes)) {
    throw new Error('Private draft asset failed exact upload read-back');
  }
  return asset;
}

module.exports = async function retainPrivateApk({github, context, core, anonymousFetch = fetch}) {
  const pr = context.payload.pull_request;
  if (context.eventName !== 'pull_request' ||
      pr?.head?.repo?.full_name !== `${context.repo.owner}/${context.repo.repo}`) {
    throw new Error('Device-test retention requires a same-repository PR');
  }
  const head = pr.head.sha;
  if (!/^[a-f0-9]{40}$/.test(head) || !/^[a-f0-9]{40}$/.test(context.sha)) {
    throw new Error('Missing exact source and tested merge identities');
  }
  const commit = (await github.rest.repos.getCommit({...context.repo, ref: head})).data;
  if (!commit.commit.message.includes('[private-apk]')) {
    core.notice('No explicit [private-apk] request on this head; no draft APK created.');
    return;
  }
  const current = (await github.rest.pulls.get({...context.repo, pull_number: pr.number})).data;
  if (current.state !== 'open' || current.head.sha !== head || current.base.sha !== pr.base.sha) {
    throw new Error('PR changed while the emulator verification was running');
  }
  const quality = await qualityChecks(github, context, head);
  const root = fs.realpathSync(process.env.GITHUB_WORKSPACE);
  const base = 'app/build/outputs/apk/preview/';
  const reportBytes = readInside(root, base + 'apk-verification.json', 2 * 1024 * 1024);
  const report = JSON.parse(reportBytes.toString('utf8'));
  const apk = readInside(root, base + 'app-preview.apk', 64 * 1024 * 1024);
  validateBytes(report, apk);
  const tag = `private-review-0.11.0-${head}-${context.runId}`;
  const name = `Analyst-AI-0.11.0-preview-${head.slice(0, 7)}.apk`;
  const body = [
    'Только ручная проверка владельцем. 0.11.0 ещё в разработке; это не завершённый выпуск.',
    'Не публиковать этот draft и не переносить APK в канал обновления Timeweb.',
    'Неотладочный preview: Android 17+, прежний package ru.omnicio.app.debug и сертификат.',
    'Проверены установка, обновление с 0.10.0/34 и запуск на API37 с измеренными страницами 16KB и 4KB; полный UI проверен в отдельной debug-сборке на синтетических данных.',
    'Физический телефон, live-брокер, платные модели и незавершённые функции 0.11.0 этим не подтверждены. Сервер не обновлялся; новые backend-функции могут быть недоступны.',
    `PR head: ${head}; tested merge: ${context.sha}; Android run: ${context.runId}.`,
    `Sonar check: ${quality.sonar}; Backend CI: ${quality.backend}.`,
    `APK SHA-256: ${report.sha256}; bytes: ${apk.length}.`,
  ].join('\n\n');
  const releases = await github.paginate(github.rest.repos.listReleases,
    {...context.repo, per_page: 100});
  let release = releases.find(item => item.tag_name === tag);
  if (!release) {
    release = (await github.rest.repos.createRelease({...context.repo, tag_name: tag,
      target_commitish: context.sha, name: 'Analyst AI 0.11.0 — ручная проверка, не выпуск',
      body: body + '\n\nUpload verification pending.', draft: true, prerelease: true,
      make_latest: 'false'})).data;
  }
  if (!release.draft) throw new Error('Refusing to modify a published release');
  await inaccessibleWithoutAuth(context.repo, `releases/${release.id}`, anonymousFetch);
  const asset = await retainAsset(github, context.repo, release, name, apk,
    'application/vnd.android.package-archive');
  await inaccessibleWithoutAuth(context.repo, `releases/assets/${asset.id}`, anonymousFetch);
  await retainAsset(github, context.repo, release, 'apk-verification.json', reportBytes, 'application/json');
  release = (await github.rest.repos.updateRelease({...context.repo, release_id: release.id,
    body: body + '\n\nAPK и отчёт повторно скачаны из GitHub; размеры и SHA-256 совпали.',
    draft: true, prerelease: true, make_latest: 'false'})).data;
  core.info('PRIVATE_APK_REVIEW=' + JSON.stringify({head, tested_merge: context.sha,
    run: context.runId, release_id: release.id, release_url: release.html_url,
    asset_id: asset.id, asset_url: asset.browser_download_url, sha256: report.sha256,
    bytes: apk.length, draft: true, timeweb_updated: false}));
  await core.summary.addHeading('Private device-test APK — no Timeweb deployment')
    .addRaw(`${release.html_url}\n\n${body}`).write();
};
module.exports.validateBytes = validateBytes;
