# Preview50 — confirmed host-test failures and narrow corrections

Source56a31b0f861442b0306d2188adad0d4e05ecbb12 was tested as merge
0c15e599b920f685735931e19c35b5005864fc4b against main
f54912165127bfab42673743cd141d635e20881f. No APK50 is published.

Android40560636884/job122388488482 ran on LAPTOP-NPSGA016 and finished FAILED
at2026-10-27T18:41:17Z. Exact source, signing certificate, Java profile, isolated
venv/dependencies, source audit and five workspace guards passed. The host suite
ran1338 tests with3 existing skips,2 failures and7 errors. Gradle, JVM tests,
APK assembly, installation and publication were not reached.

Two failures are stale version expectations in test_android17_live_spectrum and
test_spectrum_brand_identity:49/0.14.2 instead of the candidate50/0.14.3. Only
those exact expected identities change. All SDK, package, preview, artwork,
accessibility and native-rendering assertions remain intact.

The seven long-path test errors occurred during cleanup of temporary Git
fixtures: Windows refused deletion of read-only Git objects (WinError5).
Cleanup now handles only PermissionError from unlink on a regular read-only
file within its own newly created fixture, makes that file writable and retries.
Unrelated errors are re-raised. No host policy or non-fixture path is changed.
All long-path inclusion, tamper, missing-file, size-limit and hardlink tests remain.
These fixes need an actual rerun; original failed evidence is preserved.

Backend40560636877/job122388447584 passed2161 tests+1557subtests, compilation,
health/OpenAPI and existing CI regressions. Its overall result FAILED strict
Sonar122389530468. Source SHA256:
36fd6e8a3adfb52d356cd6f58382fdcf22c3191e222aa41bc87ce0394a4fd0f0.
JUnit SHA256:a6bd9ed01b6e42ce75cf81a07492a6b69f28a7cd0b0f84a3f6c1f967291d8a5.
Evidence artifact12760483546 is retained. One Starlette/AnyIO warning remains.
Sonar is not waived or declared fixed by this host-test repair.

No workflow, permissions, secrets, signing keys, remote transport, main,
production database, runtime setting or APK channel changes in this commit.
