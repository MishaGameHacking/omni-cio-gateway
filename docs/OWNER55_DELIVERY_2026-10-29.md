# Analyst AI — owner preview 55 / 0.19.0-preview: доставка 29.10.2026

**Статус:** опубликован в существующем owner preview канале. **Установка на физическом телефоне и полная native-матрица НЕ подтверждены.** Это промежуточная доставка, не полный промышленный выпуск и не завершение N00–N11.

## Проверенные идентичности

- Source commit: `b69169abb4e750985ba79bf4c08f8f0f1a2ef596` (ветка `codex/owner-system-2026-10-29`).
- Windows/WSL build/check: [40914747142](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40914747142), оба jobs `verify` и `verify-client` SUCCESS, `LAPTOP-NPSGA016`. Backend: 2370 passed, 1566 subtests passed, 1 warning; Android/JVM/lint/signing/build checks SUCCESS. Это не native acceptance.
- Exact-source `SonarCloud Code Analysis`: SUCCESS, 0 **new** issues на указанном commit; старые замечания не объявляются устранёнными.
- Render verification: [40919273008](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40919273008) SUCCESS, source commit совпадает; Layoutlib/Compose screenshot render не заменяет нативный запуск на телефоне.
- Runtime deployment: [40919271605](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40919271605) SUCCESS на действующий Timeweb9417611; старые данные, owner/session/broker binding должны сохраняться.
- Публикация: [40921809768](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40921809768), SUCCESS в 17:30 UTC (20:30 МСК), [артефакт `owner55-shell-delivery-40921809768`](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40921809768).
- Package: `ru.omnicio.app.debug`; versionCode **55**, versionName `0.19.0-preview`; minSdk **37** (Android 17+).
- APK: **29,807,943 bytes**; SHA256 **`85fd8b63a2b0fb627d7e9211bac4453efc48dfbeb31066b25ff17878fdd02896`**.
- Прежний signing certificate SHA256: **`bbce9534fd4cfee8f3bdcaf51a31cce384a4f303f090c8cae9ec558227d59eb1`** (сохранён).
- URL опубликованных точных байтов: https://analyst-ai-2941515.twc1.net/client/apk/Analyst-AI-55-85fd8b63a2b0fb627d7e9211bac4453efc48dfbeb31066b25ff17878fdd02896.apk
- Previous public versionCode: **54**. Откат/повторную публикацию не выполняли.

## Серверная проверка доставки

В журнальной квитанции `SERVER_SHELL_PUBLIC_VERIFIED` run 40921809768:
`publication.status=published`, `https_policy_verified=true`,
`https_entire_apk_verified=true`, `backend_health=200`,
`physical_phone_verified=false`, `full_native_matrix_passed=false`,
`native_acceptance=false`. Подтверждены size и SHA256 всей опубликованной HTTPS-копии.
Внешняя независимая проверка в среде мониторинга 29.10.2026 не прошла из-за DNS, а прямое HTTPS на закреплённый IP недоступно; квитанция выпуска и независимая проверка — разные свидетельства.

## Незакрытые проверки и ограничения

- **Физический телефон:** нет ADB / независимой аттестации версии, факта установки, обновления или запуска. Клиентский отчёт версии не является подтверждением установленного APK. Android может потребовать системное согласие. Совместимость только при Android 17 (API 37) и выше.
- **Native/UI:** полная матрица, реальные emulator install/upgrade/launch и длительные сценарии не закрыты. Выпуск не означает полного завершения плана.
- **AI:** [40920081275](https://github.com/MishaGameHacking/omni-cio-gateway/actions/runs/40920081275) FAILURE (`unexpected_administrative_failure`, `not_activated`, автоматический retry запрещён). Платные вызовы не включены. Реальные поручения брокеру не включены.
- Никакие дополнительные сборки, новое развёртывание, откат, ресурсы или merge в `main` мониторингом не запускались.

Это фиксация подтверждённой доставки и качества по журналам Actions, без заявления о фактическом обновлении телефона.
