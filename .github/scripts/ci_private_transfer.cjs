/* Temporary, unpublished CI input handoff; never a device-test or production release. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const ASSET = 'ci-handoff.zip';
const MAX_BYTES = 512 * 1024 * 1024;
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function identity(context, env) {
  const attempt = env.GITHUB_RUN_ATTEMPT;
  const kind = env.CI_TRANSFER_KIND || 'apk-inputs';
  if (context.eventName !== 'push' || !/^[a-f0-9]{40}$/.test(context.sha) ||
      !/^[1-9]\d{0,19}$/.test(String(context.runId)) || !/^[1-9]\d{0,4}$/.test(attempt) ||
      !['probe', 'apk-inputs'].includes(kind) ||
      context.payload.repository?.full_name !== `${context.repo.owner}/${context.repo.repo}`) {
    throw new Error('CI transfer requires an exact same-repository push identity');
  }
  return {tag: `ci-transfer-${context.runId}-${attempt}`, head: context.sha,
    body: JSON.stringify({purpose: 'temporary-private-ci-transfer', head: context.sha,
      run: context.runId, attempt, kind})};
}

function owned(release, id) {
  if (!Number.isSafeInteger(release?.id) || release.id <= 0 || release.draft !== true ||
      release.prerelease !== true || release.published_at !== null ||
      release.tag_name !== id.tag || release.target_commitish !== id.head || release.body !== id.body ||
      !Array.isArray(release.assets) || release.assets.length > 1 ||
      release.assets.some(asset => asset.name !== ASSET)) {
    throw new Error('CI transfer draft ownership, privacy or contents changed');
  }
  return release;
}

async function find(github, repo, id) {
  const releases = await github.paginate(github.rest.repos.listReleases, {...repo, per_page: 100});
  const matches = releases.filter(release => release.tag_name === id.tag);
  if (matches.length > 1) throw new Error('Ambiguous CI transfer draft');
  return matches.length ? owned(matches[0], id) : null;
}

async function inaccessibleWithoutAuth(repo, suffix, anonymousFetch) {
  const url = `https://api.github.com/repos/${repo.owner}/${repo.repo}/${suffix}`;
  const response = await anonymousFetch(url, {redirect: 'manual',
    headers: {accept: suffix.startsWith('releases/assets/')
      ? 'application/octet-stream' : 'application/vnd.github+json'}, signal: AbortSignal.timeout(20000)});
  await response.body?.cancel();
  if (response.status !== 404) throw new Error('CI draft must return 404 without authentication; received HTTP ' + response.status);
}

async function absent(call) {
  try { await call(); }
  catch (error) {
    if (error.status === 404) return true;
    throw error;
  }
  return false;
}

async function create(github, repo, id, anonymousFetch) {
  if (await find(github, repo, id)) throw new Error('CI draft already exists; clean up before retrying');
  if (!await absent(() => github.rest.git.getRef({...repo, ref: `tags/${id.tag}`}))) {
    throw new Error('Refusing an existing CI transfer tag');
  }
  const release = owned((await github.rest.repos.createRelease({...repo,
    tag_name: id.tag, target_commitish: id.head, body: id.body,
    name: 'Temporary CI input transfer — do not publish', draft: true,
    prerelease: true, make_latest: 'false', generate_release_notes: false})).data, id);
  await inaccessibleWithoutAuth(repo, `releases/${release.id}`, anonymousFetch);
  return release;
}

async function verifiedBytes(github, repo, release, expected) {
  const asset = release.assets[0];
  if (!asset || !Number.isSafeInteger(asset.id) || !Number.isSafeInteger(asset.size) ||
      asset.size <= 0 || asset.size > MAX_BYTES || asset.state !== 'uploaded' ||
      !/^[a-f0-9]{64}$/.test(expected)) throw new Error('Invalid CI transfer asset');
  const bytes = Buffer.from((await github.rest.repos.getReleaseAsset({...repo,
    asset_id: asset.id, headers: {accept: 'application/octet-stream'}})).data);
  if (bytes.length !== asset.size || digest(bytes) !== expected) {
    throw new Error('CI transfer digest or size mismatch');
  }
  return bytes;
}

async function upload({github, context, core, id, bytes, anonymousFetch}) {
  if (!bytes.length || bytes.length > MAX_BYTES) throw new Error('CI input exceeds size bound');
  const repo = context.repo;
  const release = await create(github, repo, id, anonymousFetch);
  const asset = (await github.rest.repos.uploadReleaseAsset({...repo, release_id: release.id,
    name: ASSET, data: bytes, headers: {'content-type': 'application/zip', 'content-length': bytes.length}})).data;
  const current = owned((await github.rest.repos.getRelease({...repo, release_id: release.id})).data, id);
  await inaccessibleWithoutAuth(repo, `releases/assets/${asset.id}`, anonymousFetch);
  await verifiedBytes(github, repo, current, digest(bytes));
  core.setOutput('archive_sha256', digest(bytes));
  core.info('CI_PRIVATE_TRANSFER_UPLOAD=' + JSON.stringify({bytes: bytes.length,
    sha256: digest(bytes), release_id: release.id, anonymous_access: false}));
}

async function cleanup({github, context, core, id}) {
  const repo = context.repo;
  const release = await find(github, repo, id);
  if (release) {
    await github.rest.repos.deleteRelease({...repo, release_id: release.id});
    if (!await absent(() => github.rest.repos.getRelease({...repo, release_id: release.id}))) {
      throw new Error('CI transfer draft deletion not confirmed');
    }
  }
  const ref = `tags/${id.tag}`;
  if (!await absent(() => github.rest.git.getRef({...repo, ref}))) {
    if (!release) throw new Error('Cannot attribute an orphan tag to this transfer');
    const tag = (await github.rest.git.getRef({...repo, ref})).data;
    if (tag.object.type !== 'commit' || tag.object.sha !== id.head) {
      throw new Error('Refusing a changed CI transfer tag');
    }
    await github.rest.git.deleteRef({...repo, ref});
    if (!await absent(() => github.rest.git.getRef({...repo, ref}))) {
      throw new Error('CI transfer tag deletion not confirmed');
    }
  }
  core.info('CI_PRIVATE_TRANSFER_CLEANUP=verified_absent');
}

function archivePath(env) {
  const root = fs.realpathSync(env.RUNNER_TEMP);
  const file = path.join(root, ASSET);
  if (fs.existsSync(file) && (!fs.lstatSync(file).isFile() || fs.lstatSync(file).isSymbolicLink())) {
    throw new Error('CI archive must be a regular temporary file');
  }
  return file;
}

async function transfer({github, context, core, command, env = process.env, anonymousFetch = fetch}) {
  const id = identity(context, env);
  const args = {github, context, core, id, anonymousFetch};
  if (command === 'cleanup') return cleanup(args);
  if (command === 'probe') {
    if (env.CI_TRANSFER_KIND !== 'probe') throw new Error('Synthetic transfer identity required');
    return upload({...args, bytes: Buffer.from('Synthetic private CI transfer probe\n')});
  }
  const file = archivePath(env);
  if (command === 'upload') {
    if (fs.statSync(file).size > MAX_BYTES) throw new Error('CI archive exceeds size bound');
    return upload({...args, bytes: fs.readFileSync(file)});
  }
  if (command !== 'download') throw new Error('Unsupported CI transfer command');
  const release = await find(github, context.repo, id);
  if (!release) throw new Error('CI transfer draft is missing');
  await inaccessibleWithoutAuth(context.repo, `releases/${release.id}`, anonymousFetch);
  const bytes = await verifiedBytes(github, context.repo, release, env.TRANSFER_SHA256);
  owned((await github.rest.repos.getRelease({...context.repo, release_id: release.id})).data, id);
  fs.writeFileSync(file, bytes);
  core.info('CI_PRIVATE_TRANSFER_DOWNLOAD=exact_archive_digest_verified');
}

module.exports = transfer;
module.exports.identity = identity;
module.exports.owned = owned;
