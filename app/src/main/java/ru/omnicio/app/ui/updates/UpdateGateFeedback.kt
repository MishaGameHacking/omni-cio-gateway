package ru.omnicio.app.ui.updates

/** Policy polling and the user-started operation have independent outcomes.
 * A successful periodic policy read must not erase a failed download/permission
 * message. This presentation state never decides whether a build may run.
 */
data class UpdateGateFeedback(
    val policyError: String? = null,
    val operationError: String? = null,
) {
    val message: String?
        get() = listOfNotNull(policyError?.takeIf(String::isNotBlank), operationError?.takeIf(String::isNotBlank))
            .distinct().joinToString("\n\n").takeIf(String::isNotBlank)

    fun policyChecked(problem: String? = null): UpdateGateFeedback = copy(policyError = problem)
    fun operationStarted(): UpdateGateFeedback = copy(operationError = null)
    fun operationFailed(problem: String): UpdateGateFeedback = copy(operationError = problem)
}
