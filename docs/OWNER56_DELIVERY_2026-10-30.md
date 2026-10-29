# Analyst AI 56 — delivery and remaining limits

Version56 (`0.20.0-preview`) was published on 2026-10-29 at23:14UTC, after the matching backend was deployed to the existing Timeweb server9417611. This is a preview release; physical-phone and full native acceptance are not claimed.

[Download APK56](https://analyst-ai-2941515.twc1.net/client/apk/Analyst-AI-56-93214b73634e772ca427110eda946bb6a529feb2b79663eb86b5ead0f2666e6b.apk)

## Behavior delivered

- The Android research screen reads the persistent server corpus, with search, report/news filters, pagination, source status and observation dates. Personal saved research remains accessible.
- Official original PDF retention is implemented in SQLite alongside extracted text, with SHA-256 deduplication, referenced-version retention and a separate256MiB ceiling. Existing eligible reports are requeued through the normal collection rules. Actual original retention remains unverified against live documents because their public hosts currently time out.
- Chat displays rejected estimates and job failures; brief greetings and general answers no longer require invented evidence claims. Existing cost, settlement and replay controls remain active.
- Risk, notification, analysis, candidate and document explanations resolve their evidence on the server. Existing drafts are preserved unless the owner chooses replacement. An explanation button prepares a question; it does not automatically send a paid request.
- Notification scheduling is reconciled on foreground resume using saved preferences. Android permission and background scheduling limits still apply.
- A narrow rounded icon rail opens a vertical labelled menu; duplicate bottom navigation is hidden when the rail is present. The portfolio chart has an interactive line/area view of real stored observations, preserves missing intervals and does not label deposits as returns.

## Evidence

| Check | Result |
| --- | --- |
| Application source | `a9574656fcac4507660c872ebcc22641154a3c8a` |
| Laptop verification | [40966175873](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40966175873), both backend and Android passed on LAPTOP-NPSGA016/WSL |
| Backend |2395 tests plus1566 subtests passed |
| Android JVM |296 tests,0 failures/errors/skips; lint, signing and build passed |
| Source quality |Sonar success,0 new findings |
| Visual rendering |[40966299174](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40966299174):41 PNG hashes verified;16 required previews personally inspected; no blocking layout defect observed |
| Server deployment |[40969026216](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40969026216): all8 installed module hashes matched, health200, protected routes401, owner/configuration preserved, database backup created |
| Real chat |[40971415337](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40971415337): one user message, one nonempty assistant response, completed job, saved in the database |
| APK publication |[40971636557](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40971636557): HTTPS policy and every public APK byte verified |

The first live-check wrapper rejected its receipt because the server ID was missing; database inspection also confirmed no chat request had been accepted. The quote was1.781820₽, above the initial1₽ test ceiling. After correcting the receipt and testing a2₽ ceiling, one request completed. This quote is a conservative upper bound, not the provider invoice. The application limits95₽/day and2900₽/calendar month and provider limits100₽/day and2900₽/30days were unchanged.

APK SHA-256: `93214b73634e772ca427110eda946bb6a529feb2b79663eb86b5ead0f2666e6b`,29857095 bytes. Package `ru.omnicio.app.debug`, original signing certificate `bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1`, API37 and portrait orientation preserved.

## Remaining live limits

The final bounded inspection [40971774905](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40971774905) found563 corpus publications,2 report texts,0 original PDFs and36 partial/failed collection targets. TLS handshakes from Timeweb to `www.moex.com`, `fs.moex.com` and `www.gazprom.ru` timed out; GDELT returned429. No certificate verification, robots rules or retry delays were disabled. Broker snapshot refresh completed without an error; the inspected snapshot was360 seconds old and contained3797 news items. Public-corpus documents and snapshot news are different datasets and must not be added together.

Discovery remained partial. Cash availability alone does not establish complete evidence or authorize a trade. Real brokerage orders were not enabled or sent.

Automatic renewal of the24-hour AI pricing proof is still not installed. [PR894](https://github.com/MishaGameHacking/omni-cio-gateway/pull/894) awaits the protected main branch's required authoritative check. A successful current chat request does not prove uninterrupted future availability after that pricing proof expires.

No claim is made to read all news, cover every issuer, exactly reproduce all reference images, or complete physical-device acceptance. The remaining data-source failures and pricing-renewal gate prevent calling the entire requested autonomous workflow complete.

