# Timeweb Actions import: implementation and observed access blocker

The owner requested a public HTTPS URL from which the GPT editor can import the
corrected Timeweb schema. The owner permits direct main changes, Timeweb usage
and publication of a completed APK. This change implements the schema and a
read-only hosting discovery probe; it does not deploy the investment app or
certify an APK.

## Schema

`integrations/timeweb/projects.openapi.json` describes exactly one GET action,
`listTimewebProjects`. It includes explicit `components.schemas`, internal
references and Bearer authentication. It contains no credential values. The owner confirmed on 21 October 2026 that this repository is public.
Its source visibility does not establish successful access to Timeweb or an
application deployment. An authenticated
GitHub raw URL, expiring token URL or sandbox attachment is not a durable public
URL for GPT Actions.

## Hosting discovery without resource mutations

`Timeweb Actions preflight` runs offline regression tests. A manual run on main,
or a matching push with `[timeweb-actions-probe]` in the message, then executes
three independent GET requests using the existing `TIMEWEB_CLOUD_TOKEN` Actions
secret. The fixed endpoints are projects, servers and S3 buckets.

Only numeric resource IDs, counts, explicit completeness indicators and fixed
error codes are printed. Names, passwords, access keys and original API response
bodies are not printed. Redirects are refused; each call has a timeout and a
response size cap. No cloud token is supplied to the test step by this workflow.

No cloud resources are created, deleted, resized or made public by this probe.
A first page without a matching `meta.total` is explicitly incomplete. Findings
apply only to resources visible to the token. Any endpoint failure retains a
nonzero exit code, even when other endpoint reads succeed. Access denial is not
reported as an empty account or as successful publication.

On Windows the probe uses native certificate-chain verification through
`truststore==0.10.5`, installed into an isolated per-run virtual environment from
a hash-pinned wheel. `CERT_REQUIRED`, hostname verification and TLS 1.2 minimum
are mandatory. There is no unverified fallback or retry with weaker settings.
The requirements file belongs to the probe, not the production backend.

## Observed results (2026-10-21 UTC)

1. Code commit `92326c41b451909471375c0e3f44ec63176d68fd`, run `39530920225`,
   job `118996350506`: 26 tests passed. The credentialed request failed before an
   HTTP response with a transport error. The secret was present and masked.
2. Follow-up `fbab6667e19fa186f09cffa04f61e4f2a3477456`, run `39531333782`:
   29 tests passed; typed diagnostics identified TLS certificate verification.
3. Commit `220301ad28300bfbd44a375f8b592e3e3e2cdd45` introduced an invalid
   job-level `runner.temp` expression. This was a workflow defect, not an app or
   Timeweb failure. Commit `b2a89bb9f0426936563fc188c08d78b07c635457` corrected it
   by resolving `RUNNER_TEMP` within the runner step and using `GITHUB_ENV`.
4. Run `39532074960` on `b2a89bb`: native verified TLS setup and all 33 tests
   passed. The projects request reached HTTP and returned 403.
5. Final CODE commit `69335a0a9daa7da4144be2773518103e5b8e1f14`, run
   `39532595104`, job `119001761131`: environment preparation succeeded and
   **37 test methods passed** (`Ran 37 tests in 0.136s; OK`). The live step
   attempted all three fixed endpoints independently and failed with:

```json
{
  "failed_resources": {
    "buckets": "timeweb_http_403",
    "projects": "timeweb_http_403",
    "servers": "timeweb_http_403"
  },
  "resources": {},
  "resource_changes": false,
  "public_schema_published": false,
  "ready_for_import": false
}
```

The final workflow is **failed**, not green: offline tests passed but live access
was denied. We do not suppress this failure. There is no observed inventory, no
public import URL and no evidence that the account has no resources. Original
error bodies were deliberately not logged, so the precise denial policy or
upstream/intermediary origin of 403 is not established by this diagnostic.

The token referenced by this workflow is the repository Actions secret. It is
not automatically the key stored separately in the user's custom GPT editor.
Their equality, current validity and permissions have not been verified. Do not
extract either secret into logs, files or chat to compare them. Check/update the
repository secret through GitHub's protected settings, then rerun the existing
manual workflow. Check the corresponding Timeweb token's scope and validity;
do not conclude from this result that the owner never granted permissions.

## Publication remains pending

After identifying a suitable existing endpoint, publish **only** the public
schema there, verify HTTPS and the unauthenticated response bytes, then supply
that observed URL. Do not expose this private repository, create a paid server
just for a tiny schema, extract the Actions secret, or invent an endpoint.

## Test scope

```text
python -m unittest discover -s tools/tests -p "test_timeweb_*.py" -v
```

The final local subset also passed 37 methods. Tests use mocked HTTP; live access
results are reported separately above. This pass did not run the whole-project
Backend/Android/Sonar acceptance suite and cannot certify main as entirely green.
No installation, emulator execution, physical-phone run, new APK, live backend
change, broker transaction or successful schema publication is claimed.

Project requirements remain a personal Android 17+ investment chat with a
professional 2D interface. This helper is infrastructure tooling, not the app's
chat or broker API. Telegram/server/app callback and session tests remain part
of application acceptance; this probe does not validate them.

## References

- https://timeweb.cloud/api-docs-data/bundle.json
- https://timeweb.cloud/docs/account-management/token
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
- https://help.openai.com/en/articles/9442513-gpt-actions-domain-settings-chatgpt-enterprise
