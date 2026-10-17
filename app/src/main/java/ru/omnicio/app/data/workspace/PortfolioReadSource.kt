package ru.omnicio.app.data.workspace

import androidx.compose.runtime.staticCompositionLocalOf
import org.json.JSONObject
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.market.WorkspaceClient
import ru.omnicio.app.data.portfolio.PortfolioDataClient
import ru.omnicio.app.data.research.ResearchClient

/** Read-only data dependency of portfolio presenters. Production keeps the existing authenticated clients. */
interface PortfolioReadSource {
    fun workspace(token: String, path: String, parameters: Map<String, String>): BackendResult<JSONObject>
    fun account(token: String, accountId: String, section: String, parameters: Map<String, String>): BackendResult<JSONObject>
    fun research(token: String): BackendResult<JSONObject>
}

private object NetworkPortfolioReadSource : PortfolioReadSource {
    override fun workspace(token: String, path: String, parameters: Map<String, String>) =
        WorkspaceClient().read(token, path, parameters)

    override fun account(token: String, accountId: String, section: String, parameters: Map<String, String>) =
        PortfolioDataClient().details(token, accountId, section, parameters)

    override fun research(token: String) = ResearchClient().read(token)
}

/** Synthetic implementations exist only in src/debug; no fallback or fixture is packaged in release. */
val LocalPortfolioReadSource = staticCompositionLocalOf<PortfolioReadSource> { NetworkPortfolioReadSource }
