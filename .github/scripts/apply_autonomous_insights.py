from __future__ import annotations

import base64
import json
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_DIR = Path(__file__).with_name("autonomous_bundle")
BUNDLE = "".join(path.read_text(encoding="ascii") for path in sorted(BUNDLE_DIR.glob("part*.txt")))
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
