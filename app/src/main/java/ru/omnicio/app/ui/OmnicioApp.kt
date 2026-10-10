package ru.omnicio.app.ui

import android.content.Context
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import ru.omnicio.app.R
import java.util.UUID

private const val PREFS = "omnicio_local_profile"
private const val KEY_INSTALLATION_ID = "installation_id"
private const val KEY_ONBOARDING_COMPLETE = "onboarding_complete"
private const val ROUTE_ONBOARDING = "onboarding"
private const val ROUTE_OVERVIEW = "overview"
private const val ROUTE_PORTFOLIO = "portfolio"
private const val ROUTE_ASSISTANT = "assistant"

private data class Destination(val label: String, val marker: String, val route: String)

private val mainDestinations = listOf(
    Destination("Обзор", "●", ROUTE_OVERVIEW),
    Destination("Портфель", "◆", ROUTE_PORTFOLIO),
    Destination("Помощник", "✦", ROUTE_ASSISTANT),
)

@Composable
fun OmnicioApp() {
    val context = LocalContext.current
    val profile = remember { LocalProfile(context.applicationContext) }
    val navController = rememberNavController()
    val start = if (profile.onboardingComplete) ROUTE_OVERVIEW else ROUTE_ONBOARDING

    NavHost(navController = navController, startDestination = start) {
        composable(ROUTE_ONBOARDING) {
            OnboardingScreen(
                installationId = profile.installationId,
                onTryLocal = {
                    profile.completeOnboarding()
                    navController.navigate(ROUTE_OVERVIEW) {
                        popUpTo(ROUTE_ONBOARDING) { inclusive = true }
                    }
                },
            )
        }
        composable(ROUTE_OVERVIEW) {
            MainShell(ROUTE_OVERVIEW, navController::navigateMain) {
                OverviewScreen(profile.installationId)
            }
        }
        composable(ROUTE_PORTFOLIO) {
            MainShell(ROUTE_PORTFOLIO, navController::navigateMain) {
                PortfolioScreen()
            }
        }
        composable(ROUTE_ASSISTANT) {
            MainShell(ROUTE_ASSISTANT, navController::navigateMain) {
                AssistantScreen()
            }
        }
    }
}

private fun NavHostController.navigateMain(route: String) {
    navigate(route) {
        popUpTo(ROUTE_OVERVIEW) { saveState = true }
        launchSingleTop = true
        restoreState = true
    }
}

private class LocalProfile(context: Context) {
    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    val installationId: String = prefs.getString(KEY_INSTALLATION_ID, null)
        ?: UUID.randomUUID().toString().also {
            prefs.edit().putString(KEY_INSTALLATION_ID, it).apply()
        }

    val onboardingComplete: Boolean
        get() = prefs.getBoolean(KEY_ONBOARDING_COMPLETE, false)

    fun completeOnboarding() {
        prefs.edit().putBoolean(KEY_ONBOARDING_COMPLETE, true).apply()
    }
}

@Composable
private fun OnboardingScreen(installationId: String, onTryLocal: () -> Unit) {
    var showBrokerInfo by remember { mutableStateOf(false) }

    Surface(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 36.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            Image(
                painter = painterResource(R.drawable.omnicio_logo),
                contentDescription = "Логотип OMNICIO",
                modifier = Modifier.width(72.dp),
            )
            Text(
                text = "OMNICIO",
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.semantics { heading() },
            )
            Text(
                text = "Инвестиционная аналитика с локальным персональным контуром.",
                style = MaterialTheme.typography.titleMedium,
            )

            InfoCard(
                "Данные портфеля — на устройстве",
                "Базовый режим не требует email, телефона или аккаунта OMNICIO. Демо-портфель работает без сети.",
            )
            InfoCard(
                "Общий анализ — отдельно",
                "Timeweb получает только запросы общего аналитического слоя. Broker token и суммы портфеля туда не отправляются.",
            )
            InfoCard(
                "T-Invest — только read-only",
                "Подключение будет прямым с устройства. В UI-01 кнопка показывает права и не просит токен.",
            )

            Button(
                onClick = onTryLocal,
                modifier = Modifier.fillMaxWidth(),
                contentPadding = PaddingValues(vertical = 14.dp),
            ) {
                Text("Попробовать локально")
            }
            TextButton(
                onClick = { showBrokerInfo = true },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Подключить T-Invest read-only")
            }

            HorizontalDivider()
            Text(
                text = "Локальный ID: " + installationId.take(8) + "…",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = "Минимальная ОС: Android 13 (API 33). Демо-данные всегда помечаются отдельно.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }

    if (showBrokerInfo) {
        AlertDialog(
            onDismissRequest = { showBrokerInfo = false },
            title = { Text("T-Invest read-only") },
            text = {
                Text(
                    "Подключение появится на системном этапе. Сейчас приложение не запрашивает, " +
                        "не передаёт и не сохраняет брокерский токен.",
                )
            },
            confirmButton = {
                TextButton(onClick = { showBrokerInfo = false }) { Text("Понятно") }
            },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MainShell(
    selected: String,
    onNavigate: (String) -> Unit,
    content: @Composable () -> Unit,
) {
    BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
        val wide = maxWidth >= 700.dp
        if (wide) {
            Row(modifier = Modifier.fillMaxSize()) {
                NavigationRail(modifier = Modifier.fillMaxHeight()) {
                    mainDestinations.forEach { destination ->
                        NavigationRailItem(
                            selected = destination.route == selected,
                            onClick = { onNavigate(destination.route) },
                            icon = { Text(destination.marker) },
                            label = { Text(destination.label) },
                        )
                    }
                }
                Scaffold(
                    topBar = { TopAppBar(title = { Text("OMNICIO · ДЕМО") }) },
                    modifier = Modifier.weight(1f),
                ) { padding ->
                    ScreenContainer(padding, content)
                }
            }
        } else {
            Scaffold(
                topBar = { TopAppBar(title = { Text("OMNICIO · ДЕМО") }) },
                bottomBar = {
                    NavigationBar {
                        mainDestinations.forEach { destination ->
                            NavigationBarItem(
                                selected = destination.route == selected,
                                onClick = { onNavigate(destination.route) },
                                icon = { Text(destination.marker) },
                                label = { Text(destination.label) },
                            )
                        }
                    }
                },
            ) { padding ->
                ScreenContainer(padding, content)
            }
        }
    }
}

@Composable
private fun ScreenContainer(padding: PaddingValues, content: @Composable () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding)
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        content()
    }
}

@Composable
private fun OverviewScreen(installationId: String) {
    SectionTitle("Обзор")
    StatusChip("ДЕМО · ЛОКАЛЬНО")
    MetricCard("Капитал", "1 284 530 ₽", "Fixture, не данные брокера")
    MetricCard("Доступно", "184 900 ₽", "Fixture")
    InfoCard(
        "Существенное состояние",
        "Данных T-Invest пока нет. Интерфейс работает локально и не делает сетевых запросов портфеля.",
    )
    InfoCard(
        "Профиль устройства",
        "ID " + installationId.take(8) + "… хранится локально и не является логином.",
    )
}

@Composable
private fun PortfolioScreen() {
    SectionTitle("Портфель")
    StatusChip("ДЕМО-ДАННЫЕ")
    listOf(
        Triple("ОФЗ 26238", "34 шт.", "34%"),
        Triple("SBER", "120 шт.", "28%"),
        Triple("Денежный резерв", "184 900 ₽", "14%"),
    ).forEach { (name, amount, share) ->
        Card(
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        ) {
            Column(
                modifier = Modifier.padding(18.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text(name, fontWeight = FontWeight.SemiBold)
                Text(amount, style = MaterialTheme.typography.titleMedium)
                Text("Доля: " + share, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
    Text(
        "Неизвестные значения в будущем будут показываться как «нет данных», а не как ноль.",
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun AssistantScreen() {
    SectionTitle("Помощник")
    StatusChip("БЕЗ ЧАТА")
    InfoCard(
        "Что изменилось",
        "Сейчас показан локальный fixture. В рабочем режиме здесь будет короткая лента только существенных событий.",
    )
    InfoCard(
        "Почему это важно",
        "OMNICIO будет отделять общий факт об инструменте от персонального расчёта на устройстве.",
    )
    InfoCard(
        "Следующее действие",
        "Для UI-01 действий с реальным портфелем нет. T-Invest и системная синхронизация подключаются на следующих этапах.",
    )
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.headlineMedium,
        fontWeight = FontWeight.Bold,
        modifier = Modifier.semantics { heading() },
    )
}

@Composable
private fun StatusChip(text: String) {
    Surface(
        shape = MaterialTheme.shapes.small,
        color = MaterialTheme.colorScheme.primaryContainer,
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            color = MaterialTheme.colorScheme.onPrimaryContainer,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun MetricCard(title: String, value: String, detail: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Text(title, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(value, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text(
                detail,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun InfoCard(title: String, body: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(title, fontWeight = FontWeight.SemiBold)
            Text(body, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun OnboardingPreview() {
    OnboardingScreen(
        installationId = "12345678-1234-1234-1234-123456789abc",
        onTryLocal = {},
    )
}
