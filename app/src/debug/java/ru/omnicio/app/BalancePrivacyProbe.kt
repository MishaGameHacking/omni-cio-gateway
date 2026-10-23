package ru.omnicio.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import ru.omnicio.app.data.portfolio.ApiDecimal
import ru.omnicio.app.data.portfolio.MoneyAmount
import ru.omnicio.app.ui.home.HoldToRevealBalance
import ru.omnicio.app.ui.spectrum.SpectrumCard

/** The production privacy gesture on two disclosed synthetic amounts; no session or network. */
@Composable
internal fun BalancePrivacyProbe() {
    var taps by rememberSaveable { mutableIntStateOf(0) }
    Column(Modifier.fillMaxSize().safeDrawingPadding().semantics { testTagsAsResourceId = true }
        .testTag("workspace-content").verticalScroll(rememberScrollState()).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ", style = MaterialTheme.typography.labelSmall)
        SpectrumCard {
            HoldToRevealBalance(MoneyAmount(ApiDecimal(1000, 0), "RUB"), true, { taps++ }, Modifier.testTag("private-first"))
            HoldToRevealBalance(MoneyAmount(ApiDecimal(2000, 0), "RUB"), true, { taps++ }, Modifier.testTag("private-second"))
        }
        Text("Касаний валюты: $taps", style = MaterialTheme.typography.bodyMedium)
        Text("Каждая сумма открывается только на время удержания.", style = MaterialTheme.typography.bodySmall)
    }
}
