package ru.omnicio.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
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
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navDeepLink
import ru.omnicio.app.R
import ru.omnicio.app.ui.theme.OmniSpacing
import ru.omnicio.app.ui.theme.OmnicioTheme

private const val ROUTE_ONBOARDING = "onboarding"
private const val ROUTE_PRIVACY = "privacy"
private const val ROUTE_OVERVIEW = "overview"
private const val ROUTE_PORTFOLIO = "portfolio"
private const val ROUTE_POSITION = "position"
private const val ROUTE_ASSISTANT = "assistant"
private const val ROUTE_SETTINGS = "settings"
private const val DEEP_LINK_PREFIX = "omnicio://"

private data class Destination(
    val label: String,
    val marker: String,
    val route: String,
)

private val mainDestinations = listOf(
    Destination("Обзор", "●", ROUTE_OVERVIEW),
    Destination("Портфель", "◆", ROUTE_PORTFOLIO),
    Destination("Помощник", "✦", ROUTE_ASSISTANT),
)

@Composable
internal fun OmnicioApp(appViewModel: OmnicioViewModel = viewModel()) {
    val uiState by appViewModel.uiState.collectAsStateWithLifecycle()
    val navController = rememberNavController()
    val startDestination = if (uiState.onboardingComplete) ROUTE_OVERVIEW else ROUTE_ONBOARDING

    NavHost(
        navController = navController,
        startDestination = startDestination,
    ) {
        composable(ROUTE_ONBOARDING) {
            OnboardingScreen(
                installationId = uiState.installationId,
                onTryLocal = {
                    appViewModel.completeOnboarding()
                    navController.navigate(ROUTE_OVERVIEW) {
                        popUpTo(ROUTE_ONBOARDING) { inclusive = true }
                    }
                },
                onOpenPrivacy = { navController.navigate(ROUTE_PRIVACY) },
            )
        }
        composable(ROUTE_PRIVACY) {
            PrivacyScreen(onBack = { navController.popBackStack() })
        }
        composable(
            route = ROUTE_OVERVIEW,
            deepLinks = if (uiState.onboardingComplete) {
                listOf(navDeepLink { uriPattern = DEEP_LINK_PREFIX + ROUTE_OVERVIEW })
            } else {
                emptyList()
            },
        ) {
            MainShell(
                selected = ROUTE_OVERVIEW,
                onNavigate = navController::navigateMain,
                onOpenSettings = { navController.navigate(ROUTE_SETTINGS) },
            ) {
                OverviewScreen(
                    uiState = uiState,
                    onToggleAmounts = appViewModel::toggleAmountsHidden,
                    onCurrency = appViewModel::setDisplayCurrency,
                    onMode = appViewModel::setOverviewMode,
                )
            }
        }
        composable(
            route = ROUTE_PORTFOLIO,
            deepLinks = if (uiState.onboardingComplete) {
                listOf(navDeepLink { uriPattern = DEEP_LINK_PREFIX + ROUTE_PORTFOLIO })
            } else {
                emptyList()
            },
        ) {
            MainShell(
                selected = ROUTE_PORTFOLIO,
                onNavigate = navController::navigateMain,
                onOpenSettings = { navController.navigate(ROUTE_SETTINGS) },
                scrollable = false,
            ) {
                PortfolioScreen(
                    dataAvailable = uiState.settings.portfolioPresent,
                    onOpenPosition = { uid ->
                        navController.navigate(ROUTE_POSITION + "/" + uid)
                    },
                )
            }
        }
        composable(
            route = ROUTE_POSITION + "/{uid}",
            deepLinks = if (uiState.onboardingComplete) {
                listOf(navDeepLink { uriPattern = DEEP_LINK_PREFIX + ROUTE_POSITION + "/{uid}" })
            } else {
                emptyList()
            },
        ) { backStackEntry ->
            val uid = backStackEntry.arguments?.getString("uid").orEmpty()
            MainShell(
                selected = ROUTE_PORTFOLIO,
                onNavigate = navController::navigateMain,
                onOpenSettings = { navController.navigate(ROUTE_SETTINGS) },
            ) {
                PositionDetailScreen(
                    instrumentUid = uid,
                    dataAvailable = uiState.settings.portfolioPresent,
                    onBack = { navController.popBackStack() },
                )
            }
        }
        composable(
            route = ROUTE_ASSISTANT,
            deepLinks = if (uiState.onboardingComplete) {
                listOf(navDeepLink { uriPattern = DEEP_LINK_PREFIX + ROUTE_ASSISTANT })
            } else {
                emptyList()
            },
        ) {
            MainShell(
                selected = ROUTE_ASSISTANT,
                onNavigate = navController::navigateMain,
                onOpenSettings = { navController.navigate(ROUTE_SETTINGS) },
                scrollable = false,
            ) {
                AssistantScreen(
                    onOpenPosition = { uid ->
                        navController.navigate(ROUTE_POSITION + "/" + uid)
                    },
                )
            }
        }
        composable(
            route = ROUTE_SETTINGS,
            deepLinks = if (uiState.onboardingComplete) {
                listOf(navDeepLink { uriPattern = DEEP_LINK_PREFIX + ROUTE_SETTINGS })
            } else {
                emptyList()
            },
        ) {
            SettingsScreen(
                uiState = uiState,
                onBack = { navController.popBackStack() },
                onDeletePortfolio = appViewModel::deleteLocalPortfolio,
                onRestoreDemoPortfolio = appViewModel::restoreDemoPortfolio,
                onConnectBrokerFixture = appViewModel::connectBrokerFixture,
                onDisconnectBroker = appViewModel::disconnectBroker,
                onRevokeBrokerFixture = appViewModel::revokeBrokerFixture,
                onRetryMigration = appViewModel::retryLocalMigration,
                onReserveMinor = appViewModel::setReserveMinor,
                onGoalHorizonYears = appViewModel::setGoalHorizonYears,
                onNotificationsEnabled = appViewModel::setNotificationsEnabled,
                onFastAlertsEnabled = appViewModel::setFastAlertsEnabled,
            )
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

@Composable
private fun OnboardingScreen(
    installationId: String,
    onTryLocal: () -> Unit,
    onOpenPrivacy: () -> Unit,
) {
    var showBrokerInfo by rememberSaveable { mutableStateOf(false) }

    Surface(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(
                    horizontal = OmniSpacing.xl,
                    vertical = OmniSpacing.xxl,
                ),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.md),
        ) {
            Image(
                painter = painterResource(R.drawable.omnicio_logo),
                contentDescription = "Логотип OMNICIO",
                modifier = Modifier.size(72.dp),
            )
            Text(
                text = "OMNICIO",
                style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.semantics { heading() },
            )
            Text(
                text = "Инвестиционная аналитика с локальным персональным контуром.",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            InfoCard(
                title = "Портфель может остаться на устройстве",
                body = "Базовый режим не требует email, телефона или аккаунта OMNICIO. Демо-портфель работает без сети.",
            )
            InfoCard(
                title = "Общий рынок — отдельный слой",
                body = "Общие рыночные данные и аналитика могут приходить с Timeweb. Локальный демо-портфель туда не отправляется.",
            )
            InfoCard(
                title = "T-Invest подключается добровольно",
                body = "На UI-этапе мы только показываем режим чтения. Брокерский токен приложение ещё не запрашивает.",
            )

            Button(
                onClick = onTryLocal,
                modifier = Modifier.fillMaxWidth(),
                contentPadding = PaddingValues(vertical = 15.dp),
            ) {
                Text("Попробовать локально")
            }
            OutlinedButton(
                onClick = { showBrokerInfo = true },
                modifier = Modifier.fillMaxWidth(),
                contentPadding = PaddingValues(vertical = 15.dp),
            ) {
                Text("Подключить T-Invest только для чтения")
            }
            TextButton(
                onClick = onOpenPrivacy,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Как устроена приватность")
            }

            HorizontalDivider()
            Text(
                text = "Локальный ID: " + installationIdLabel(installationId),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = "Поддерживается Android 8.0 и новее. Демо-данные всегда помечаются отдельно.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }

    if (showBrokerInfo) {
        AlertDialog(
            onDismissRequest = { showBrokerInfo = false },
            title = { Text("T-Invest · только чтение") },
            text = {
                Text(
                    "Подключение брокера появится на системном этапе. Сейчас OMNICIO " +
                        "не просит, не передаёт и не сохраняет брокерский токен.",
                )
            },
            confirmButton = {
                TextButton(onClick = { showBrokerInfo = false }) {
                    Text("Понятно")
                }
            },
        )
    }
}

@Composable
private fun PrivacyScreen(onBack: () -> Unit) {
    Surface(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(
                    horizontal = OmniSpacing.xl,
                    vertical = OmniSpacing.xxl,
                ),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.md),
        ) {
            Text(
                text = "Приватность",
                style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.semantics { heading() },
            )
            Text(
                text = "Что остаётся локально и что может использовать общий слой OMNICIO.",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            InfoCard(
                title = "Только на устройстве",
                body = "Локальный ID установки, демо-портфель, настройки отображения и будущие персональные параметры локального режима.",
            )
            InfoCard(
                title = "Общие запросы",
                body = "Timeweb предназначен для общих рыночных данных и аналитики. UI-этап не отправляет туда суммы, позиции или демо-портфель.",
            )
            InfoCard(
                title = "Брокерский доступ",
                body = "На UI-этапе токен T-Invest отсутствует. Позже учётные данные только для чтения будут вводиться отдельно и не станет публичным логином OMNICIO.",
            )

            Button(
                onClick = onBack,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Назад")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MainShell(
    selected: String,
    onNavigate: (String) -> Unit,
    onOpenSettings: () -> Unit,
    scrollable: Boolean = true,
    content: @Composable () -> Unit,
) {
    BoxWithConstraints(modifier = Modifier.fillMaxSize()) {
        val fontScale = LocalDensity.current.fontScale
        val layoutMode = effectiveLayoutMode(maxWidth.value.toInt(), fontScale)
        val horizontalPadding = when (layoutMode) {
            AppLayoutMode.COMPACT -> OmniSpacing.sm
            AppLayoutMode.STANDARD -> OmniSpacing.lg
            AppLayoutMode.WIDE -> OmniSpacing.xl
        }
        if (layoutMode == AppLayoutMode.WIDE) {
            Row(modifier = Modifier.fillMaxSize()) {
                NavigationRail(
                    modifier = Modifier.fillMaxHeight(),
                    containerColor = MaterialTheme.colorScheme.surface,
                ) {
                    mainDestinations.forEach { destination ->
                        NavigationRailItem(
                            selected = destination.route == selected,
                            onClick = { onNavigate(destination.route) },
                            icon = {
                                Text(
                                    text = destination.marker,
                                    modifier = Modifier.clearAndSetSemantics {},
                                )
                            },
                            label = { Text(destination.label) },
                        )
                    }
                }
                Scaffold(
                    topBar = { AppTopBar(selected, onOpenSettings) },
                    modifier = Modifier.weight(1f),
                ) { padding ->
                    ScreenContainer(padding, scrollable, horizontalPadding, content)
                }
            }
        } else {
            Scaffold(
                topBar = { AppTopBar(selected, onOpenSettings) },
                bottomBar = {
                    NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
                        mainDestinations.forEach { destination ->
                            NavigationBarItem(
                                selected = destination.route == selected,
                                onClick = { onNavigate(destination.route) },
                                icon = {
                                Text(
                                    text = destination.marker,
                                    modifier = Modifier.clearAndSetSemantics {},
                                )
                            },
                                label = { Text(destination.label) },
                            )
                        }
                    }
                },
            ) { padding ->
                ScreenContainer(padding, scrollable, horizontalPadding, content)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppTopBar(
    selected: String,
    onOpenSettings: () -> Unit,
) {
    val title = mainDestinations.firstOrNull { it.route == selected }?.label ?: "OMNICIO"
    val largeFont = shouldStackDetailLine(LocalDensity.current.fontScale)
    TopAppBar(
        title = {
            Column {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleLarge,
                )
                if (!largeFont) {
                    Text(
                        text = "OMNICIO · ДЕМО",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        },
        actions = {
            TextButton(onClick = onOpenSettings) {
                Text(if (largeFont) "Настр." else "Настройки")
            }
        },
    )
}

@Composable
private fun ScreenContainer(
    padding: PaddingValues,
    scrollable: Boolean,
    horizontalPadding: Dp,
    content: @Composable () -> Unit,
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding),
    ) {
        val baseModifier = Modifier
            .widthIn(max = 960.dp)
            .fillMaxWidth()
            .align(Alignment.TopCenter)
            .padding(
                horizontal = horizontalPadding,
                vertical = OmniSpacing.md,
            )

        if (scrollable) {
            Column(
                modifier = baseModifier.verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(OmniSpacing.md),
            ) {
                content()
            }
        } else {
            Box(
                modifier = baseModifier.fillMaxSize(),
            ) {
                content()
            }
        }
    }
}

@Composable
internal fun StatusPill(text: String) {
    Surface(
        shape = MaterialTheme.shapes.small,
        color = MaterialTheme.colorScheme.primaryContainer,
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(
                horizontal = OmniSpacing.sm,
                vertical = OmniSpacing.xs,
            ),
            color = MaterialTheme.colorScheme.onPrimaryContainer,
            style = MaterialTheme.typography.labelMedium,
        )
    }
}

@Composable
internal fun InfoCard(
    title: String,
    body: String,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface,
        ),
    ) {
        Column(
            modifier = Modifier.padding(OmniSpacing.md),
            verticalArrangement = Arrangement.spacedBy(OmniSpacing.xs),
        ) {
            Text(
                text = title,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                text = body,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Preview(
    showBackground = true,
    backgroundColor = 0xFF0F1012,
)
@Composable
private fun OnboardingPreview() {
    OmnicioTheme {
        OnboardingScreen(
            installationId = "12345678-1234-1234-1234-123456789abc",
            onTryLocal = {},
            onOpenPrivacy = {},
        )
    }
}
