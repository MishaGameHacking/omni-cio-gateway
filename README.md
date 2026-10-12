# Analyst AI — Android

Чистая стартовая база Android-приложения **Analyst AI**.

- Открывайте корень репозитория в Android Studio.
- Основной модуль: `app`.
- Отображаемое название приложения: **Analyst AI**.
- Package/applicationId: `ru.omnicio.app` — сохраняется для совместимости уже установленного приложения.
- Минимальная версия устройства: Android 13 (API 33).
- Сборка выполняется через Gradle Wrapper: `gradlew` / `gradlew.bat`.
- Launcher icon сохранён.
- Главный экран: нижняя вкладка «Портфель», без демонстрационных финансовых значений.
- Нижняя вкладка «Профиль»: компактные секции «Настройки / Профиль / Инфо» и подключение T‑Invest API через «Профиль → T‑API».
- Вход в Analyst AI выполняется через Telegram OIDC; Telegram ID связывает пользователя с его аккаунтом Analyst AI.
- Пользователь сам вставляет read-only токен T‑Invest API. Backend проверяет его через GetAccounts.
- Подтверждённый T‑Invest token шифруется и хранится на Timeweb в аккаунте пользователя; в GitHub и APK токен не встраивается.
- Скриншоты разрешены по умолчанию; запрет можно включить вручную в «Профиль → Настройки».
- Будущие данные портфеля поступают из T‑Invest API пользователя; UI не подставляет выдуманные суммы.
- Backend Analyst AI развёрнут на Timeweb и использует существующие GitHub secrets/variables без раскрытия их значений.
- Старый backend, PostgreSQL и прежняя архитектура проекта не возвращаются.

## Telegram Login (Android)
 
- Основной OIDC callback в @BotFather → Login Widget → Redirect URIs:
  `https://94.198.220.228.sslip.io/auth/telegram/callback`.
- После обработки сервер пытается автоматически открыть `analystai://auth?code=…`.
  Если браузер не позволяет автоматическую передачу в Android, на странице есть
  явная кнопка **«Открыть Analyst AI»**. Клиент принимает одноразовый код,
  обменивает его на серверную сессию и сохраняет токен зашифрованным на Android.
- **Trusted Origins** требуются при браузерном JavaScript Login; текущий
  серверный OIDC с PKCE их не использует.
- **Native Login** в @BotFather нужен для нативного Telegram SDK, который
  сейчас не подключён. Регистрация сама по себе не заменяет callback
  серверного OIDC. Если переходить на SDK, нужно указать Android package
  и SHA-256 сертификата подписи *фактически установленного APK*.
- Release package: `ru.omnicio.app`. Загружаемый с GitHub debug APK
  использует `ru.omnicio.app.debug`; эти приложения не взаимозаменяемы и
  требуют отдельных настроек в Native Login.
- SHA-256 сертификата Android-приложения можно посмотреть через
  `./gradlew :app:signingReport` или `apksigner verify --print-certs <APK>`.
  Подставляйте отпечаток именно того APK, который ставите на устройство.
- Client Secret Telegram хранится только на сервере, не в Android-приложении.
- Сеанс хранится после закрытия приложения до окончания срока действия
  серверного токена (сейчас 30 суток). Удаление данных приложения,
  переустановка с удалением данных или истечение срока действия требуют нового входа.

## T-Invest API (версия 0.2.3)

- Android передаёт вставленный read-only токен на `POST /tinvest/token` по HTTPS.
- Backend проверяет токен исключительно чтением `UsersService/GetAccounts` в
  официальном production REST API T-Invest. Успешным считается только HTTP 200
  с корректным списком `accounts`. Лишь после этого токен шифруется Fernet
  и сохраняется в SQLite, привязанный к Telegram ID.
- Проверка цепочки HTTPS включена. Корневой сертификат Минцифры РФ используется
  **только** для запросов к T-Invest и дополняет обычное системное доверие:
  `backend/certs/russian_trusted_root_ca.pem`.
  Отпечаток SHA-256 X.509 DER:
  `d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31`.
  Источник: `https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt`;
  репозиторный экземпляр сверяется по указанному отпечатку при каждой проверке.
  Нельзя исправлять ошибки сертификата через `verify=False`.
- Ошибки отклонённого токена, TLS, таймаута, лимитов API и сетевого доступа
  теперь отображаются отдельно; отклонённая замена не удаляет предыдущий токен.
  Содержимое токена и тело ответа банка не пишутся в логи.
- Android не сохраняет ввод токена в `savedInstanceState` и очищает его после
  успешного подключения.

**Ограничение текущей версии:** на экране портфеля ещё нет реальной загрузки
`GetAccounts`, `GetPortfolio` и `GetPositions`. Подключение T-API
не означает, что стоимость портфеля и список позиций уже реализованы.

Текущая цель — создавать Analyst AI почти с чистого листа.

## Analyst AI 0.3.0

This iteration adds a five-tab Android shell, real read-only T-Invest portfolio loading, RUB/USD/EUR portfolio display selected by tapping the total, and a deterministic AI decision gate that prevents empty token-consuming analyses. The chosen autonomous-analysis architecture is documented in `docs/AI_ORCHESTRATION.md`.
