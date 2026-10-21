package ru.omnicio.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.unit.dp
import ru.omnicio.app.ui.spectrum.SpectrumSecondaryButton
import ru.omnicio.app.ui.workspace.rememberUserWorkspaceState

/** Exercises the production state owner; does not create or bypass an authenticated session. */
@Composable
internal fun SessionContextProbe() {
    val state = rememberUserWorkspaceState()
    var user by rememberSaveable { mutableStateOf<String?>("A") }
    Column(Modifier.fillMaxSize().safeDrawingPadding().semantics { testTagsAsResourceId = true }
        .testTag("workspace-content").verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("ВИЗУАЛЬНЫЙ ТЕСТ · НЕ РЕАЛЬНЫЕ ДАННЫЕ")
        Text("Проверка сохранения контекста. Telegram и брокер не вызываются.")
        val current = user
        if (current == null) {
            Text("Тестовый сеанс закрыт")
            for (identity in listOf("A", "B")) {
                SpectrumSecondaryButton("Войти как $identity", { user = identity },
                    Modifier.fillMaxWidth().testTag("session-login-$identity"))
            }
        } else state.Content("synthetic-context-$current") {
            var account by rememberSaveable { mutableStateOf("account-1") }
            var period by rememberSaveable { mutableStateOf("day") }
            Text("Пользователь: $current")
            Text("Счёт: $account")
            Text("Период: $period")
            SpectrumSecondaryButton("Изменить контекст", { account = "account-2"; period = "month" },
                Modifier.fillMaxWidth().testTag("session-context-change"))
            SpectrumSecondaryButton("Истечение сеанса", { user = null },
                Modifier.fillMaxWidth().testTag("session-expire"))
            SpectrumSecondaryButton("Явный выход", { state.forget(); user = null },
                Modifier.fillMaxWidth().testTag("session-logout"))
        }
    }
}
