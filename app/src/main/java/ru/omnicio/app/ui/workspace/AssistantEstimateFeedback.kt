package ru.omnicio.app.ui.workspace

import ru.omnicio.app.data.workspace.ChatRouteQuote
import ru.omnicio.app.data.workspace.VolumeWorkspaceClient

/** HTTP 200 can still deny a quote; the current draft must show that denial. */
internal fun assistantEstimateFeedback(quote: ChatRouteQuote?, current: Boolean, reason: String?): String? {
    if (!current || quote == null || quote.usable) return null
    return VolumeWorkspaceClient.chatPolicyMessage(reason) ?:
        "Сервер не подтвердил маршрут или стоимость ответа. Вопрос не отправлен модели; проверьте подключение и повторите проверку."
}
