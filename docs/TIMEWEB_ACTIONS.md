# Timeweb Actions import: verified first step

This change does not deploy the investment app or authorize publication of an
untested APK. The owner requested a public HTTPS URL from which the GPT editor
can import the corrected Timeweb schema.

`integrations/timeweb/projects.openapi.json` describes exactly one GET action,
`listTimewebProjects`. It includes explicit `components.schemas`, internal
references and Bearer authentication. It contains no credential values. This
private repository is a source copy, **not** a public import URL. An authenticated
GitHub raw URL, expiring token URL or sandbox attachment is not a durable public
URL for GPT Actions.

## Hosting discovery without changes or charges

`Timeweb Actions preflight` runs offline regression tests. A manual run on main,
or a matching push with `[timeweb-actions-probe]` in the message, then executes
three GET requests using the existing `TIMEWEB_CLOUD_TOKEN` Actions secret.
Only numeric resource IDs, counts and explicit completeness indicators are
printed. Names, passwords, access keys and original API response bodies are not
printed. Redirects are refused; each call has a timeout and a response size cap.
No token is available to the test step through this workflow configuration.

No resources are created, deleted, resized, exposed or charged by this probe.
A first page without a matching `meta.total` is explicitly incomplete. Findings
apply only to resources visible to the token. The result explicitly records
`public_schema_published=false` and `ready_for_import=false`.

After identifying a suitable existing endpoint, publish **only** the public
schema there, verify HTTPS and the unauthenticated response bytes, then supply
that observed URL. Do not expose this private repository, create a paid server
just for a tiny schema, extract the Actions secret, or invent an endpoint.
If the secret is missing, expired or permission-limited, the workflow fails with
a fixed diagnostic instead of presenting an empty account as successful access.

## Local tests

```text
python -m unittest discover -s tools/tests -p "test_timeweb_*.py" -v
```

The initial offline run passed 26 methods using mocked HTTP, not a live Timeweb
account. Actual access and URL publication need their own observed results.

## API references

- https://timeweb.cloud/api-docs-data/bundle.json
- https://timeweb.cloud/docs/account-management/token
- https://help.openai.com/en/articles/9442513-gpt-actions-domain-settings-chatgpt-enterprise

Project requirements remain a personal Android 17+ investment chat with a
professional 2D interface. The helper is infrastructure tooling, not the app's
chat or broker API. The previous Telegram/server/app callback and session tests
remain part of application acceptance; this probe does not validate them.

## First real probe (2026-10-21 UTC)

Commit `92326c41b451909471375c0e3f44ec63176d68fd`, Actions run
`39530920225`, job `118996350506`: all 26 tests passed on the Windows runner.
The secret was present (masked); the live read failed with
`TIMEWEB_ACTIONS_ERROR=timeweb_transport_error`. This is NOT an HTTP 401/403
result and does not establish whether the credential is authorized. No inventory
or public URL was obtained. TLS verification was not disabled.

The follow-up categorizes DNS, certificate, handshake, timeout and connection
errors using exception types only, without printing their messages or adding
a retry. Local follow-up suite: 29 passing methods.
