# OMNICIO 2.6.0 — RuStore release-candidate checklist

Статус: checklist для серверного Android-клиента. Он не означает, что приложение уже опубликовано.

## Identity

- package/applicationId: `ru.omnicio.app`;
- versionName: `2.6.0`;
- versionCode: `8`;
- первая опубликованная release signature после публикации становится частью неизменяемой identity приложения;
- private release/upload key, keystore и пароли не хранятся в Git и не передаются в PR/chat.

## Сборка

Debug используется только для разработки и QA.

Release packaging разрешён только при наличии защищённых локальных/CI значений:

- `OMNICIO_RELEASE_STORE_FILE`;
- `OMNICIO_RELEASE_STORE_PASSWORD`;
- `OMNICIO_RELEASE_KEY_ALIAS`;
- `OMNICIO_RELEASE_KEY_PASSWORD`.

Без них Gradle обязан отказать в `assembleRelease` / `bundleRelease`, чтобы случайно не принять unsigned/debug-signed артефакт за store candidate.

Перед публикацией:

1. exact accepted main SHA подтверждён;
2. Android lint/unit/debug build и release-source compile зелёные;
3. Sonar: 0 unresolved/accepted new issues и 0 security hotspots;
4. подписанный APK/AAB собирается только из accepted release commit;
5. подпись проверяется отдельно до загрузки;
6. package/versionCode/versionName сверяются с карточкой RuStore.

## RuStore upload

RuStore принимает APK и AAB. Для первой APK-версии файл должен быть подписан цифровым сертификатом, package должен быть уникальным, а сборка — проверенной. Для последующих версий package и подпись должны совпадать с предыдущими, а номер версии должен увеличиваться.

Для AAB подпись приложения/ключ загрузки настраиваются в RuStore отдельно до загрузки bundle.

Официальные источники:
- https://www.rustore.ru/help/developers/publishing-and-verifying-apps/app-publication
- https://www.rustore.ru/help/developers/publishing-and-verifying-apps/app-publication/new-version-app/upload-aab
- https://www.rustore.ru/help/developers/publishing-and-verifying-apps/app-publication/apk-signature

## Screenshots

Перед отправкой на модерацию снять screenshots с exact signed release candidate, а не со старого debug build.

Набор:
1. Обзор;
2. Портфель;
3. Помощник;
4. Настройки (рекомендуется как четвёртый кадр).

Деморежима нет. Использовать только реальные разрешённые данные или пустые состояния; не публиковать персональные сведения. FLAG_SECURE не отключать в production ради скриншотов.

Текущие требования RuStore для мобильных screenshots:
- 1–10 изображений;
- PNG или JPG;
- до 3 МБ;
- не выше 2160×3840;
- рекомендуемое соотношение сторон 16:9.

Источник:
https://www.rustore.ru/help/developers/publishing-and-verifying-apps/app-publication

## Privacy / permissions

Перед upload сверить release manifest с `legal/android-privacy-declaration.md`.
Android 2.6.0 ожидает только `INTERNET`; push permission отсутствует. Появление нового чувствительного permission требует отдельной проверки декларации и store metadata.

## Остановка выпуска

Не публиковать, если:
- release build собран не из accepted SHA;
- подпись не подтверждена;
- Android Studio/CI показывает unresolved build error;
- manifest permissions отличаются от декларации;
- screenshot или описание заявляет функцию, которой нет в exact release;
- package/version identity расходится с RuStore.

