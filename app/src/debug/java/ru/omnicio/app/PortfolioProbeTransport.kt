package ru.omnicio.app

import java.net.URI
import java.net.URLDecoder
import java.time.LocalDate
import kotlinx.coroutines.flow.MutableStateFlow
import org.json.JSONArray
import org.json.JSONObject
import ru.omnicio.app.data.backend.BackendResult
import ru.omnicio.app.data.workspace.PortfolioReadSource
import ru.omnicio.app.data.workspace.VolumeReply
import ru.omnicio.app.data.workspace.WorkspaceTransport

internal data class PortfolioProbeCall(val sequence: Int, val method: String, val path: String,
    val parameters: Map<String, String>, val status: Int) {
    fun json(): JSONObject = JSONObject().put("sequence", sequence).put("method", method).put("path", path)
        .put("parameters", JSONObject(parameters)).put("status", status)
}

internal data class PortfolioProbeTrace(val calls: List<PortfolioProbeCall> = emptyList(),
    val count: Int = 0, val errors: List<String> = emptyList())

/** A bounded read-only server substitute. It never constructs a network client. */
internal class PortfolioProbeTransport(val scenario: String, val data: PortfolioProbeData = PortfolioProbeData()) :
    PortfolioReadSource, WorkspaceTransport {
    val trace = MutableStateFlow(PortfolioProbeTrace())
    private var weekFailureDelivered = false
    private val instrumentIds = data.snapshot().accounts.flatMap { it.positions }.map { it.id }.toSet()
    private val accountIds = data.snapshot().accounts.map { it.id }.toSet()

    override fun workspace(token: String, path: String, parameters: Map<String, String>): BackendResult<JSONObject> =
        read(token, path, parameters).asBackendResult()

    override fun account(token: String, accountId: String, section: String,
        parameters: Map<String, String>): BackendResult<JSONObject> =
        read(token, "/tinvest/accounts/$accountId/$section", parameters).asBackendResult()

    override fun research(token: String): BackendResult<JSONObject> =
        read(token, "/analysis/research", emptyMap()).asBackendResult()

    @Synchronized
    override fun request(token: String, path: String, method: String, body: JSONObject?): VolumeReply {
        val parsed = runCatching {
            val uri = URI(path)
            require(!uri.isAbsolute && uri.rawFragment == null)
            val pairs = uri.rawQuery?.split('&')?.filter(String::isNotBlank)?.map { pair ->
                val split = pair.split('=', limit = 2)
                require(split.size == 2)
                URLDecoder.decode(split[0], "UTF-8") to URLDecoder.decode(split[1], "UTF-8")
            }.orEmpty()
            require(pairs.map { it.first }.distinct().size == pairs.size)
            uri.path to pairs.toMap()
        }.getOrElse { return reject(method, path.take(180), emptyMap(), "Некорректный путь тестового запроса") }
        if (method != "GET" || body != null)
            return reject(method, parsed.first, parsed.second, "Этот сценарий разрешает только чтение; отправка в ИИ не моделируется")
        return read(token, parsed.first, parsed.second)
    }

    @Synchronized
    private fun read(token: String, path: String, parameters: Map<String, String>): VolumeReply {
        if (token != PORTFOLIO_PROBE_TOKEN) return reject("GET", path, parameters, "Неверный синтетический сеанс")
        return try {
            val reply = when {
                path == "/workspace" -> {
                    validateKeys(parameters, setOf("currency", "start", "end"))
                    require(parameters["currency"] == "RUB")
                    validatePeriod(parameters, required = false)
                    success(data.workspace())
                }
                path == "/analysis/research" -> {
                    require(parameters.isEmpty()); success(data.research())
                }
                path == "/workspace/markets/calendar" -> {
                    require(parameters.isEmpty()); success(data.tradingCalendar())
                }
                path == "/workspace/risks" -> {
                    require(parameters == mapOf("currency" to "RUB")); success(data.risks())
                }
                path == "/workspace/chat/threads" -> {
                    require(parameters.isEmpty())
                    success(data.obj("items" to JSONArray(listOf(data.obj("thread_id" to PORTFOLIO_PROBE_THREAD,
                        "title" to "СИНТЕТИЧЕСКИЙ диалог для проверки контекста", "updated_at" to data.asOf)))))
                }
                path == "/workspace/chat/threads/$PORTFOLIO_PROBE_THREAD/messages" -> {
                    require(parameters.isEmpty())
                    success(data.obj("items" to JSONArray(), "has_more" to false, "next_before" to null))
                }
                path.startsWith("/workspace/instruments/") -> instrument(path, parameters)
                path.startsWith("/tinvest/accounts/") -> accountData(path, parameters)
                else -> return reject("GET", path, parameters, "Маршрут не входит в контракт портфельного сценария")
            }
            record("GET", path, parameters, reply.status)
            reply
        } catch (_: IllegalArgumentException) {
            reject("GET", path, parameters, "Параметры не соответствуют контракту портфельного сценария")
        } catch (_: Exception) {
            reject("GET", path, parameters, "Не удалось сформировать изолированный ответ сценария")
        }
    }

    private fun instrument(path: String, parameters: Map<String, String>): VolumeReply {
        val parts = path.split('/')
        require(parts.size == 5 && parts[3] in instrumentIds)
        val uid = parts[3]
        return when (parts[4]) {
            "dossier" -> { require(parameters.isEmpty()); success(data.dossier(uid)) }
            "candles" -> {
                validateKeys(parameters, setOf("start", "end", "interval"))
                validatePeriod(parameters, required = true)
                require(parameters["interval"] in setOf("hour", "day", "week", "month"))
                if (parameters["interval"] == "week" && !weekFailureDelivered) {
                    weekFailureDelivered = true
                    VolumeReply(error = "СИНТЕТИЧЕСКИЙ источник временно недоступен. Повторите чтение выбранной недели.",
                        code = "synthetic_read_unavailable", status = 503, retryable = true)
                } else success(data.candles(uid, parameters))
            }
            else -> throw IllegalArgumentException("unsupported instrument resource")
        }
    }

    private fun accountData(path: String, parameters: Map<String, String>): VolumeReply {
        val parts = path.split('/')
        require(parts.size == 5 && parts[3] in accountIds)
        return when (parts[4]) {
            "analytics" -> {
                validateKeys(parameters, setOf("start", "end", "currency", "history_resolution"))
                require(parameters["currency"] == "RUB")
                require(parameters["history_resolution"] == null || parameters["history_resolution"] in setOf("intraday", "hour", "day"))
                validatePeriod(parameters, required = false)
                success(data.analytics(parameters, scenario == "partial"))
            }
            else -> throw IllegalArgumentException("unsupported account resource")
        }
    }

    private fun validateKeys(parameters: Map<String, String>, keys: Set<String>) {
        require(parameters.keys.all { it in keys } && parameters.values.all { it.length <= 300 })
    }

    private fun validatePeriod(parameters: Map<String, String>, required: Boolean) {
        val start = parameters["start"]?.let(LocalDate::parse)
        val end = parameters["end"]?.let(LocalDate::parse)
        require(!required || start != null && end != null)
        require(start == null || end == null || start <= end)
        require(start == null || start >= data.day.minusYears(10))
        require(end == null || end <= data.day)
    }

    private fun success(value: JSONObject) = VolumeReply(data = JSONObject(value.toString()), status = 200)
    private fun VolumeReply.asBackendResult(): BackendResult<JSONObject> = this.data?.let { BackendResult.Success(it) }
        ?: BackendResult.Failure(error ?: "СИНТЕТИЧЕСКИЙ ответ не получен", retryable, status)

    private fun record(method: String, path: String, parameters: Map<String, String>, status: Int, error: String? = null) {
        val previous = trace.value
        val call = PortfolioProbeCall(previous.count + 1, method, path, parameters.toSortedMap(), status)
        trace.value = PortfolioProbeTrace((previous.calls + call).takeLast(64), previous.count + 1,
            if (error == null) previous.errors else (previous.errors + error).takeLast(16))
    }

    private fun reject(method: String, path: String, parameters: Map<String, String>, error: String): VolumeReply {
        record(method, path, parameters, 422, error)
        return VolumeReply(error = "СИНТЕТИЧЕСКИЙ тест: $error", code = "synthetic_contract_rejected", status = 422)
    }
}

/** Retain the synthetic server across rotation; process restarts correctly make fresh reads. */
internal object PortfolioProbeSessions {
    private val sessions = linkedMapOf<String, PortfolioProbeTransport>()
    @Synchronized fun transport(userId: String, scenario: String): PortfolioProbeTransport =
        sessions.getOrPut("$userId:$scenario") { PortfolioProbeTransport(scenario) }.also {
            while (sessions.size > 8) sessions.remove(sessions.keys.first())
        }
}
