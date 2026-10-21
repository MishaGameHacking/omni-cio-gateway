'use strict';

const {newestSonarCheck, assertCleanSonar} = require('./require_clean_sonar.cjs');

module.exports = async function requireMainRelease({github, context}) {
  const requested = context.eventName === 'workflow_dispatch' ||
    (context.eventName === 'push' && context.payload.head_commit?.message?.includes('[publish-apk]'));
  if (!requested || context.ref !== 'refs/heads/main' || !/^[a-f0-9]{40}$/.test(context.sha) ||
      context.payload.repository?.full_name !== `${context.repo.owner}/${context.repo.repo}`) {
    throw new Error('Publication requires an explicit request on the exact main commit');
  }
  const checks = await github.paginate(github.rest.checks.listForRef,
    {...context.repo, ref: context.sha, per_page: 100});
  const sonar = newestSonarCheck(checks, context.sha);
  const annotations = sonar ? await github.paginate(github.rest.checks.listAnnotations,
    {...context.repo, check_run_id: sonar.id, per_page: 100}) : [];
  assertCleanSonar(sonar, annotations, context.sha);
  const runs = await github.paginate(github.rest.actions.listWorkflowRunsForRepo,
    {...context.repo, head_sha: context.sha, event: 'push', per_page: 100});
  const backend = runs.filter(run => run.name === 'Backend CI' && run.head_sha === context.sha &&
    run.path === '.github/workflows/backend-ci.yml' && run.event === 'push')
    .sort((a, b) => b.id - a.id)[0];
  if (backend?.status !== 'completed' || backend.conclusion !== 'success') {
    throw new Error('Exact-head Backend CI must pass before publication');
  }
  const current = (await github.rest.git.getRef({...context.repo, ref: 'heads/main'})).data;
  if (current.object?.type !== 'commit' || current.object.sha !== context.sha) {
    throw new Error('Main moved after verification; this run cannot publish');
  }
  return {head: context.sha, sonar: sonar.id, backend: backend.id};
};
