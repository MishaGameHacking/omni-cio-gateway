# Owner system 55 server release

This staging patch is not a deployment or a test receipt. Execute the synthetic
installer tests only on LAPTOP-NPSGA016 through owner-system-tools55.yml.

The runtime baseline is 9bf6dbaea3625a6479691e71365b621d965358c6. Its backend tree
18e96683e1483df214429bd6ed9065bdb9662b2f is identical to the last deployed source
a88ea60c71c4d19942ccf1892ceba50213e6e528. The installer still verifies every expected
runtime module against its exact bytes before stopping or replacing anything.
An unexpected runtime change blocks the release.

The reviewed delta is exactly these sixteen production modules:

```
ai_broker_access.py ai_budget.py ai_guarded_client.py app.py credit_evidence.py
owner_app.py owner_password.py owner_password_routes.py portfolio_mandate.py
purchase_policy.py strategy_construction.py strategy_profiles.py volume_credit.py
volume_market.py volume_purchases.py volume_workspace.py
```

The source packager must use this same baseline and exact delta. Before publication,
replace all PIN placeholders in workspace-deploy.yml with the reviewed final source
commit, full successful owner-system.yml run, artifact and bundle SHA-256, successful
owner-system-tools55.yml run and exact tested tools commit. Both verify and
verify-client jobs must succeed. Exact-source Sonar and installer file identities
remain mandatory; the placeholders deliberately cannot deploy.
The deployment workflow is triggered only when its own file changes. Publish this
frozen workflow together with the tools changes: its one placeholder run fails
before deployment, while later installer-only commits run tests without launching
a stale deployment. Replace the placeholders in a separate reviewed final release.

Deployment targets only existing Timeweb server 9417611. The existing SSH transport
and its pinned administration checkout are unchanged. The installer preserves the
owner binding, backend.env (including encryption key and credentials), database,
and APK update policy. It backs up SQLite before activation and checks public
health, protected routes, private password status headers and GET rejection on
password write routes. It never enrolls an owner, attempts a password, reads token
values, creates a brokerage action, changes automation settings, or restores the
database from a backup.

Ordinary activation failure restores only source files. After password enrollment,
the database blocks old login routes; downgrading code would remove the owner's
working password login. If credentials appear during activation, the rollback
guard retains installed candidate files and owner credentials and records
rollback_requires_auth_compatible_recovery. Unknown database state also blocks
downgrade. Recovery then needs password-compatible code. The guard does not stop
a healthy service merely because rollback is blocked. Activation failure may
already have stopped services; the guard does not restart incompatible old code.
The concurrent-enrollment case is covered by a synthetic test. No credential
trigger is dropped and no owner account or database is reset.

Partial service startup is included in the activation failure handler. Both
services must stop successfully and report inactive/failed with zero main and
control PIDs before the credential rollback check. A failed stop, unknown service
state or lingering process retains the candidate files and reports
rollback_requires_service_quiescence. It never restores old source while an owner
process could still enroll credentials. Synthetic tests cover partial start,
failed stop, a lingering process and healthy activation without shutdown.
