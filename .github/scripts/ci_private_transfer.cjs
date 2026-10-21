/* Temporary, unpublished CI input handoff; never a device-test or production release. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const ASSET = 'ci-handoff.zip';
const MAX_BYTES = 512 * 1024 * 1024;
const digest = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

function identity(context, env) {
  const attempt = env.GITHUB_RUN_ATTEMPT;
  const repository = `${context.repo.owner}/${context.repo.repo}`;
  const sameRepositoryEvent = context.eventName === 'push' ||
    (context.eventName === 'pull_request' && context.payload.pull_request?.head?.repo?.full_name === repository);
  const target = context.eventName === 'pull_request' ? context.payload.pull_request?.head?.sha : context.sha;
  if (!sameRepositoryEvent || !/^[a-f0-9]{40}$/.test(context.sha) || !/^[a-f0-9]{40}$/.test(target) ||
      !/^[1-9]\d{0,19}$/.test(String(context.runId)) || !/^[1-9]\d{0,4}$/.test(attempt) ||
      context.payload.repository?.full_name !== repository) {
    throw new Error('CI transfer requires an exact same-repository event identity');
  }
  return {tag: `ci-transfer-${context.runId}-${attempt}`, head: context.sha, target,
    body: JSON.stringify({purpose: 'temporary-private-ci-transfer', head: context.sha,
      target, run: context.runId, attempt})};
}

function owned(release, id) {
  if (!Number.isSafeInteger(release?.id) || release.id <= 0 || release.draft !== true ||
      release.prerelease !== true || release.published_at !== null ||
      release.tag_name !== id.tag || release.target_commitish !== id.target || release.body !== id.body ||
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
    tag_name: id.tag, target_commitish: id.target, body: id.body,
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

async function storeBytes({github, context, id, bytes, anonymousFetch}, release) {
  if (!bytes.length || bytes.length > MAX_BYTES) throw new Error('CI input exceeds size bound');
  const repo = context.repo;
  const asset = (await github.rest.repos.uploadReleaseAsset({...repo, release_id: release.id,
    name: ASSET, data: bytes, headers: {'content-type': 'application/zip', 'content-length': bytes.length}})).data;
  const current = owned((await github.rest.repos.getRelease({...repo, release_id: release.id})).data, id);
  await inaccessibleWithoutAuth(repo, `releases/assets/${asset.id}`, anonymousFetch);
  await verifiedBytes(github, repo, current, digest(bytes));
  return asset;
}

async function prepare(args) {
  const {github, context, core, id, anonymousFetch} = args;
  const release = await create(github, context.repo, id, anonymousFetch);
  const asset = await storeBytes({...args, bytes: Buffer.from('Synthetic private CI transfer probe\n')}, release);
  await github.rest.repos.deleteReleaseAsset({...context.repo, asset_id: asset.id});
  const current = owned((await github.rest.repos.getRelease({...context.repo, release_id: release.id})).data, id);
  if (current.assets.length !== 0) throw new Error('Synthetic transfer asset deletion not confirmed');
  core.info('CI_PRIVATE_TRANSFER_PREPARED=private_readback_passed_and_empty_draft_retained');
}

async function upload(args) {
  const {github, context, core, id, bytes, anonymousFetch} = args;
  const release = await find(github, context.repo, id);
  if (!release || release.assets.length !== 0) throw new Error('Empty preflight-owned CI draft is required');
  await inaccessibleWithoutAuth(context.repo, `releases/${release.id}`, anonymousFetch);
  await storeBytes(args, release);
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
    if (tag.object.type !== 'commit' || tag.object.sha !== id.target) {
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
  if (command === 'prepare') return prepare(args);
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
module.exports.inaccessibleWithoutAuth = inaccessibleWithoutAuth;
