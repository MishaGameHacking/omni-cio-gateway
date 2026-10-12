from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, found {count}: {old[:120]!r}")
    write(path, content.replace(old, new, 1))


def append_once(path: str, marker: str, block: str) -> None:
    content = read(path)
    if marker in content:
        return
    write(path, content.rstrip() + "\n\n" + block.strip() + "\n")


# Keep the scheduler portable on Windows CI images that do not bundle IANA tzdata.
replace_once(
    "backend/autonomous_ai.py",
    """from datetime import UTC, datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo""",
    """from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Mapping""",
)
replace_once(
    "backend/autonomous_ai.py",
    'MOSCOW = ZoneInfo("Europe/Moscow")',
    'MOSCOW = timezone(timedelta(hours=3), name="Europe/Moscow")',
)

# Start/stop the autonomous scheduler with the FastAPI process.
replace_once(
    "backend/app.py",
    """@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield
""",
    """@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    try:
        from .autonomous_ai import init_autonomous_db, start_scheduler, stop_scheduler
    except ImportError:
        from autonomous_ai import init_autonomous_db, start_scheduler, stop_scheduler

    init_autonomous_db()
    scheduler_task = start_scheduler()
    try:
        yield
    finally:
        await stop_scheduler(scheduler_task)
""",
)
append_once(
    "backend/app.py",
    "autonomous_ai_router",
    """
try:
    from .autonomous_ai import router as autonomous_ai_router
except ImportError:
    from autonomous_ai import router as autonomous_ai_router

app.include_router(autonomous_ai_router)
""",
)

# Publish the feature as Android 0.4.0.
replace_once(
    "app/build.gradle.kts",
    '        versionCode = 17\n        versionName = "0.3.0"',
    '        versionCode = 18\n        versionName = "0.4.0"',
)

# Replace placeholder tabs with real analysis screens and add profile routing.
main_path = "app/src/main/java/ru/omnicio/app/MainActivity.kt"
replace_once(
    main_path,
    """import ru.omnicio.app.ui.LocalAnalystTabNavigator
import ru.omnicio.app.ui.PlaceholderTabScreen
import ru.omnicio.app.ui.auth.TelegramLoginScreen""",
    """import ru.omnicio.app.ui.LocalAnalystTabNavigator
import ru.omnicio.app.ui.analysis.AnalysisProfileSettingsScreen
import ru.omnicio.app.ui.analysis.IdeasScreen
import ru.omnicio.app.ui.analysis.InsightFeedScreen
import ru.omnicio.app.ui.analysis.PulseScreen
import ru.omnicio.app.ui.auth.TelegramLoginScreen""",
)
replace_once(
    main_path,
    """    Chat,
    Profile,
    TApi,""",
    """    Chat,
    Profile,
    AnalysisSettings,
    TApi,""",
)

main = read(main_path)
start = main.index("                        AppScreen.Ideas -> {")
end = main.index("                        AppScreen.Profile -> {", start)
analysis_tabs = """                        AppScreen.Ideas -> {
                            IdeasScreen(
                                accessToken = current.accessToken,
                                onPortfolioClick = {
                                    screenName = AppScreen.Portfolio.name
                                },
                                onProfileClick = {
                                    screenName = AppScreen.Profile.name
                                },
                                onOpenProfileSettings = {
                                    screenName = AppScreen.AnalysisSettings.name
                                },
                            )
                        }

                        AppScreen.Pulse -> {
                            PulseScreen(
                                accessToken = current.accessToken,
                                onPortfolioClick = {
                                    screenName = AppScreen.Portfolio.name
                                },
                                onProfileClick = {
                                    screenName = AppScreen.Profile.name
                                },
                            )
                        }

                        AppScreen.Chat -> {
                            InsightFeedScreen(
                                accessToken = current.accessToken,
                                onPortfolioClick = {
                                    screenName = AppScreen.Portfolio.name
                                },
                                onProfileClick = {
                                    screenName = AppScreen.Profile.name
                                },
                            )
                        }

"""
main = main[:start] + analysis_tabs + main[end:]
write(main_path, main)

replace_once(
    main_path,
    """                                onOpenTApi = {
                                    screenName = AppScreen.TApi.name
                                },
                                onLogout = {""",
    """                                onOpenTApi = {
                                    screenName = AppScreen.TApi.name
                                },
                                onOpenAnalysisSettings = {
                                    screenName = AppScreen.AnalysisSettings.name
                                },
                                onLogout = {""",
)
replace_once(
    main_path,
    """                        AppScreen.TApi -> {
                            TApiScreen(""",
    """                        AppScreen.AnalysisSettings -> {
                            AnalysisProfileSettingsScreen(
                                accessToken = current.accessToken,
                                onBack = {
                                    screenName = AppScreen.Profile.name
                                },
                                onPortfolioClick = {
                                    screenName = AppScreen.Portfolio.name
                                },
                                onProfileClick = {
                                    screenName = AppScreen.Profile.name
                                },
                            )
                        }

                        AppScreen.TApi -> {
                            TApiScreen(""",
)

# Add the autonomous analysis profile entry to the Profile screen.
profile_path = "app/src/main/java/ru/omnicio/app/ui/profile/ProfileScreen.kt"
replace_once(
    profile_path,
    """    onPortfolioClick: () -> Unit,
    onOpenTApi: () -> Unit,
    onLogout: () -> Unit,""",
    """    onPortfolioClick: () -> Unit,
    onOpenTApi: () -> Unit,
    onOpenAnalysisSettings: () -> Unit,
    onLogout: () -> Unit,""",
)
replace_once(
    profile_path,
    """                    item {
                        ProfileCard(
                            title = "Данные портфеля",
                            subtitle = "Счета и позиции из T‑Invest API",
                            symbol = "₽",
                        )
                    }
                    item {
                        ProfileCard(
                            title = user.name?.takeIf { it.isNotBlank() } ?: "Telegram",""",
    """                    item {
                        ProfileCard(
                            title = "Инвестиционный профиль",
                            subtitle = "Риск, горизонт, резерв и фоновые обзоры",
                            symbol = "AI",
                            onClick = onOpenAnalysisSettings,
                        )
                    }
                    item {
                        ProfileCard(
                            title = "Данные портфеля",
                            subtitle = "Счета и позиции из T‑Invest API",
                            symbol = "₽",
                        )
                    }
                    item {
                        ProfileCard(
                            title = user.name?.takeIf { it.isNotBlank() } ?: "Telegram",""",
)

append_once(
    "README.md",
    "Analyst AI 0.4.0",
    """
## Analyst AI 0.4.0

- autonomous portfolio snapshots and morning/evening checks;
- deterministic material-change and critical-risk gates before any paid AI call;
- per-user daily AI budgets, cooldown and digest deduplication;
- persistent insight feed, Pulse, risk-profile settings and class-level diversification ideas;
- fail-closed operation: algorithmic safety cards remain available when no AI runtime key is configured.
""",
)

print("Autonomous Analyst AI v0.4 integration applied")
