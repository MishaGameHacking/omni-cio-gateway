from __future__ import annotations

import base64
import json
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = "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[...truncated...]
FILES = json.loads(zlib.decompress(base64.b64decode(BUNDLE)).decode("utf-8"))


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def append_once(path: str, marker: str, block: str) -> None:
    content = read(path)
    if marker in content:
        return
    write(path, content.rstrip() + "\n\n" + block.strip() + "\n")


def replace_braced_block(path: str, marker: str, replacement: str) -> None:
    content = read(path)
    start = content.find(marker)
    if start < 0:
        if replacement.strip() in content:
            return
        raise RuntimeError(f"{path}: block marker not found")
    open_index = content.find("{", start)
    if open_index < 0:
        raise RuntimeError(f"{path}: opening brace not found")
    depth = 0
    in_string = False
    escaped = False
    triple = False
    i = open_index
    while i < len(content):
        if content.startswith('"""', i) and not escaped:
            triple = not triple
            i += 3
            continue
        ch = content[i]
        if not triple:
            if ch == '"' and not escaped:
                in_string = not in_string
            if in_string:
                escaped = (ch == '\\' and not escaped)
                if ch != '\\':
                    escaped = False
                i += 1
                continue
        if not in_string and not triple:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    write(path, content[:start] + replacement + content[i + 1:])
                    return
        i += 1
    raise RuntimeError(f"{path}: matching closing brace not found")


for path, payload in FILES.items():
    write(path, payload)

# FastAPI application: persistent schema, autonomous runtime and insight routes.
app_path = "backend/app.py"
app = read(app_path)
if "from . import insights_store" not in app and "import insights_store" not in app:
    app = app.replace(
        "from pydantic import BaseModel\n",
        """from pydantic import BaseModel

try:
    from . import insights_store
except ImportError:  # pragma: no cover - uvicorn top-level import compatibility
    import insights_store  # type: ignore[no-redef]
""",
        1,
    )
old_lifespan = """@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield
"""
new_lifespan = """@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    runtime_task = None
    try:
        try:
            from .insights_runtime import start_runtime, stop_runtime
        except ImportError:  # pragma: no cover - uvicorn top-level compatibility
            from insights_runtime import start_runtime, stop_runtime
        runtime_task = start_runtime()
        yield
    finally:
        if 'stop_runtime' in locals():
            await stop_runtime(runtime_task)
"""
if old_lifespan in app:
    app = app.replace(old_lifespan, new_lifespan, 1)
elif new_lifespan not in app:
    raise RuntimeError("backend/app.py lifespan anchor changed")
app = app.replace('    version="0.1.0",', '    version="0.4.0",', 1)
init_anchor = '        )\n        db.commit()\n\n\ndef hash_token'
init_replacement = '        )\n        insights_store.init_schema(db)\n        db.commit()\n\n\ndef hash_token'
if init_anchor in app:
    app = app.replace(init_anchor, init_replacement, 1)
elif 'insights_store.init_schema(db)' not in app:
    raise RuntimeError("backend/app.py init_db anchor changed")
write(app_path, app)
append_once(
    app_path,
    "insights_api_router",
    """
try:
    from .insights_api import router as insights_api_router
except ImportError:
    from insights_api import router as insights_api_router

app.include_router(insights_api_router)
""",
)

# Preserve richer instrument metadata in server snapshots for risk analysis.
portfolio_path = "backend/tinvest_portfolio.py"
portfolio = read(portfolio_path)
if '"instrumentType": instrument_type' not in portfolio:
    portfolio = portfolio.replace(
        '                "id": identifier,\n                "title": _position_title(raw, ticker),',
        '                "id": identifier,\n                "instrumentUid": identifier,\n                "instrumentType": instrument_type,\n                "title": _position_title(raw, ticker),',
        1,
    )
if '"instrumentType": "cash"' not in portfolio:
    portfolio = portfolio.replace(
        '                "id": identifier,\n                "title": CURRENCY_NAMES.get(currency, currency),',
        '                "id": identifier,\n                "instrumentUid": identifier,\n                "instrumentType": "cash",\n                "title": CURRENCY_NAMES.get(currency, currency),',
        1,
    )
write(portfolio_path, portfolio)

# Runtime settings are installed on the Timeweb host without exposing secrets.
deploy_path = ".github/scripts/deploy_timeweb_backend.sh"
deploy = read(deploy_path)
if "ANALYST_RUNTIME_ENABLED=1" not in deploy:
    deploy = deploy.replace(
        "DATABASE_PATH=/var/lib/analyst-ai/backend.db\nEOF",
        """DATABASE_PATH=/var/lib/analyst-ai/backend.db
ANALYST_RUNTIME_ENABLED=1
ANALYST_RUNTIME_TIMEZONE=Europe/Moscow
ANALYST_RUNTIME_POLL_SECONDS=300
ANALYST_PORTFOLIO_POLL_SECONDS=900
ANALYST_MORNING_TIME=09:45
ANALYST_EVENING_TIME=19:15
AI_DAILY_FAST_CALLS=12
AI_DAILY_STANDARD_CALLS=4
AI_DAILY_PREMIUM_CALLS=1
PUBLIC_MARKET_FACTS_ENABLED=1
PUBLIC_MARKET_FACT_REFRESH_SECONDS=1800
TIMEWEB_AI_TOKEN=$TIMEWEB_AI_TOKEN
TIMEWEB_AI_BASE_URL=${TIMEWEB_AI_BASE_URL:-https://api.timeweb.ai/v1}
AI_MODEL_FAST=$AI_MODEL_FAST
AI_MODEL_STANDARD=$AI_MODEL_STANDARD
AI_MODEL_PREMIUM=$AI_MODEL_PREMIUM
TELEGRAM_ALERT_BOT_TOKEN=${TELEGRAM_ALERT_BOT_TOKEN:-}
EOF""",
        1,
    )
write(deploy_path, deploy)

# Android dependencies and release version.
build_path = "app/build.gradle.kts"
build = read(build_path)
build = build.replace(
    '        versionCode = 17\n        versionName = "0.3.0"',
    '        versionCode = 18\n        versionName = "0.4.0"',
    1,
)
if "implementation(libs.work.runtime.ktx)" not in build:
    build = build.replace(
        "    implementation(libs.browser)\n",
        "    implementation(libs.browser)\n    implementation(libs.core.ktx)\n    implementation(libs.work.runtime.ktx)\n",
        1,
    )
write(build_path, build)

catalog_path = "gradle/libs.versions.toml"
catalog = read(catalog_path)
if 'coreKtx = "1.19.1"' not in catalog:
    catalog = catalog.replace(
        'browser = "1.10.0"\n',
        'browser = "1.10.0"\ncoreKtx = "1.19.1"\nwork = "2.11.2"\n',
        1,
    )
if "core-ktx =" not in catalog:
    catalog = catalog.replace(
        'browser = { module = "androidx.browser:browser", version.ref = "browser" }\n',
        'browser = { module = "androidx.browser:browser", version.ref = "browser" }\ncore-ktx = { module = "androidx.core:core-ktx", version.ref = "coreKtx" }\nwork-runtime-ktx = { module = "androidx.work:work-runtime-ktx", version.ref = "work" }\n',
        1,
    )
write(catalog_path, catalog)

manifest_path = "app/src/main/AndroidManifest.xml"
manifest = read(manifest_path)
if "android.permission.POST_NOTIFICATIONS" not in manifest:
    manifest = manifest.replace(
        '    <uses-permission android:name="android.permission.INTERNET" />\n',
        '    <uses-permission android:name="android.permission.INTERNET" />\n    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />\n',
        1,
    )
write(manifest_path, manifest)

# Profile links to investment limits and shows runtime/cost status.
profile_path = "app/src/main/java/ru/omnicio/app/ui/profile/ProfileScreen.kt"
profile = read(profile_path)
if "onOpenInvestmentSettings" not in profile:
    profile = profile.replace(
        """    onPortfolioClick: () -> Unit,
    onOpenTApi: () -> Unit,
    onLogout: () -> Unit,""",
        """    onPortfolioClick: () -> Unit,
    onOpenTApi: () -> Unit,
    onOpenInvestmentSettings: () -> Unit,
    insightsStatus: String,
    onLogout: () -> Unit,""",
        1,
    )
settings_anchor = """                    item {
                        ProfileCard(
                            title = "Безопасность",
                            subtitle = "Секреты скрыты и не попадают в APK",
                            symbol = "⌾",
                        )
                    }"""
settings_replacement = """                    item {
                        ProfileCard(
                            title = "Автономный Analyst AI",
                            subtitle = insightsStatus,
                            symbol = "AI",
                            accent = insightsStatus.contains("включён"),
                            onClick = onOpenInvestmentSettings,
                        )
                    }
                    item {
                        ProfileCard(
                            title = "Безопасность",
                            subtitle = "Секреты скрыты и не попадают в APK",
                            symbol = "⌾",
                        )
                    }"""
if settings_anchor in profile:
    profile = profile.replace(settings_anchor, settings_replacement, 1)
elif "Автономный Analyst AI" not in profile:
    raise RuntimeError("ProfileScreen settings anchor changed")
write(profile_path, profile)

# Android activity keeps secure login/session logic and delegates signed-in UI.
main_path = "app/src/main/java/ru/omnicio/app/MainActivity.kt"
main = read(main_path)
if "import android.Manifest" not in main:
    main = main.replace("package ru.omnicio.app\n\n", "package ru.omnicio.app\n\nimport android.Manifest\n", 1)
if "import android.os.Build" not in main:
    main = main.replace(
        "import android.os.Bundle\n",
        "import android.os.Build\nimport android.os.Bundle\nimport android.content.pm.PackageManager\n",
        1,
    )
if "import androidx.core.app.ActivityCompat" not in main:
    main = main.replace(
        "import androidx.compose.ui.tooling.preview.Preview\n",
        "import androidx.compose.ui.tooling.preview.Preview\nimport androidx.core.app.ActivityCompat\nimport androidx.core.content.ContextCompat\n",
        1,
    )
if "import ru.omnicio.app.ui.SignedInHome" not in main:
    main = main.replace(
        "import ru.omnicio.app.ui.auth.TelegramLoginScreen\n",
        "import ru.omnicio.app.ui.SignedInHome\nimport ru.omnicio.app.ui.auth.TelegramLoginScreen\n",
        1,
    )
if "requestNotificationPermissionIfNeeded()" not in main:
    main = main.replace(
        "        enableEdgeToEdge()\n",
        "        enableEdgeToEdge()\n        requestNotificationPermissionIfNeeded()\n",
        1,
    )
if "private fun requestNotificationPermissionIfNeeded" not in main:
    permission_method = """
    private fun requestNotificationPermissionIfNeeded() {
        if (
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.POST_NOTIFICATIONS,
            ) != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.POST_NOTIFICATIONS),
                420,
            )
        }
    }

"""
    main = main.replace(
        "    private fun applyScreenshotPolicy(blocked: Boolean) {",
        permission_method + "    private fun applyScreenshotPolicy(blocked: Boolean) {",
        1,
    )
write(main_path, main)
replace_braced_block(
    main_path,
    "            is AuthUiState.SignedIn -> {",
    """            is AuthUiState.SignedIn -> {
                SignedInHome(
                    accessToken = current.accessToken,
                    user = current.user,
                    tApiConfigured = tApiConfigured,
                    portfolioState = portfolioState,
                    portfolioCurrency = portfolioCurrency,
                    onPortfolioCurrencyClick = {
                        portfolioCurrencyName = portfolioCurrency.next().name
                    },
                    screenshotsBlocked = screenshotsBlocked,
                    onScreenshotsBlockedChange = { blocked ->
                        screenshotsBlocked = blocked
                        onScreenshotsBlockedChange(blocked)
                    },
                    onTApiConfiguredChange = { configured ->
                        tApiConfigured = configured
                        if (!configured) {
                            portfolioState = PortfolioUiState.NotConnected
                        }
                    },
                    onLogout = {
                        sessionStore.clear()
                        tApiConfigured = false
                        portfolioState = PortfolioUiState.NotConnected
                        authState = AuthUiState.SignedOut()
                    },
                )
            }""",
)

print(f"Applied autonomous insights transformation to {len(FILES)} generated files")
