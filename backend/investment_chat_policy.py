"""Bounded, no-network admission and complexity policy for investment chat.

This conservative lexical policy is not a trained semantic classifier or an
accuracy guarantee. Unknown topics ask for clarification, not a paid guess.
Only server-loaded, owner-scoped user questions may supply follow-up context.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from collections.abc import Sequence

try:
    from .ai_policy import AnalysisTier
except ImportError:  # uvicorn top-level imports
    from ai_policy import AnalysisTier

POLICY_VERSION = "investment-chat-v3"
SCOPE_MESSAGE = (
    "Analyst AI отвечает только на вопросы об инвестициях, активах и мировой "
    "финансовой политике. Этот запрос не относится к поддерживаемым темам."
)
CLARIFY_MESSAGE = (
    "Уточните инвестиционный вопрос: укажите актив, портфель, рыночный показатель "
    "или влияние события на финансовые рынки. Вызов модели не выполнен."
)
TIER_MESSAGE = (
    "Для этого вопроса нужен более глубокий анализ. Выберите автоматический "
    "режим или подходящую глубину; стоимость будет проверена до отправки."
)

FINANCE = re.compile(
    r"\b(?:актив\w*|капитал\w*|валют\w*|фрс|ецб|инвест\w*|портфел\w*|облигац\w*|дивиденд\w*|эмитент\w*|"
    r"дефолт\w*|банкрот\w*|котиров\w*|ребаланс\w*|диверсифик\w*|"
    r"инфляц\w*|дефляц\w*|брокер\w*|ценн\w*\s+бумаг\w*|"
    r"акци[яиюй]|акциями|акциях|ликвидност\w*|волатильност\w*|"
    r"фондов\w*|бирж\w*|купонов\w*|купон\w*|доходност\w*|"
    r"денежн\w*\s+поток\w*|ключев\w*\s+ставк\w*|"
    r"центральн\w*\s+банк\w*|финансов\w*|долгов\w*|"
    r"бухгалтер\w*|отчетност\w*|мсфо|рсбу|офз|иис|нкд|"
    r"investment\w*|portfolio\w*|bond\w*|stock\w*|equities|equity|"
    r"dividend\w*|issuer\w*|default\w*|bankrupt\w*|inflation|deflation|"
    r"rebalanc\w*|diversif\w*|securit(?:y|ies)|valuation\w*|"
    r"earnings|cash\s+flow\w*|financial\w*|monetary|fiscal|"
    r"interest\s+rates?|etf\w*|ebitda|ebit|ifrs|gaap|cvar|var)\b",
    re.IGNORECASE,
)
OUTSIDE = re.compile(
    r"\b(?:рецепт\w*|борщ\w*|приготов\w*|погод\w*|гороскоп\w*|"
    r"зодиак\w*|анекдот\w*|сказк\w*|стихотвор\w*|поздравлен\w*|"
    r"диагноз\w*|антибиотик\w*|лечени\w*|лекарств\w*|"
    r"recipe\w*|cook(?:ing)?|weather|horoscope\w*|joke\w*|poem\w*|"
    r"diagnos\w*|antibiotic\w*|medical\s+treatment)\b",
    re.IGNORECASE,
)
UNRELATED_TASK = re.compile(
    r"\b(?:напиши|сочини|придумай|сгенерируй|write|generate|compose)\b"
    r"[^.!?\n]{0,90}\b(?:код|скрипт|программ\w*|python|javascript|"
    r"стих\w*|песн\w*|рассказ\w*|роман\w*|сказк\w*|code|script|story|song)\b",
    re.IGNORECASE,
)
INJECTION = re.compile(
    r"\b(?:игнорируй|забудь|отмени|ignore|disregard|override)\b"
    r"[^.!?\n]{0,90}\b(?:инструкц\w*|правил\w*|ограничен\w*|"
    r"instructions?|rules?|restrictions?|system)\b|"
    r"\b(?:system\s+prompt|developer\s+message|системн\w*\s+промпт)\b",
    re.IGNORECASE,
)
RETAIL = re.compile(r"\bакци\w*\b[^.!?\n]{0,50}\b(?:магазин\w*|супермаркет\w*|скидк\w*)\b", re.IGNORECASE)
INTRODUCTION = frozenset({"привет", "здравствуй", "здравствуйте", "добрый день", "добрый вечер", "hello", "hi", "что ты умеешь", "как пользоваться analyst ai"})
FOLLOW_UP = frozenset({
    "почему", "поясни", "объясни", "подробнее", "что это значит", "какие риски",
    "риски", "что дальше", "приведи пример", "why", "explain", "more detail",
    "what risks", "explain the balance", "объясни влияние события",
    "разобрать возможное влияние",
})


def _follow_up(text: str) -> bool:
    question = text.rstrip("?.! ")
    for prefix in ("а какие ", "and ", "а ", "и "):
        if question.startswith(prefix):
            question = question[len(prefix):]
            break
    return question in FOLLOW_UP

DEFINITION = re.compile(r"^\s*(?:что\s+такое|что\s+означает|объясни\s+термин|what\s+is|define)\b", re.IGNORECASE)
DEEP = re.compile(
    r"\b(?:дефолт|банкрот|ковенант|реструктуризац|платежеспособ|default|bankrupt|covenant)\w*\b"
    r"|\bsolvency\b", re.IGNORECASE,
)
STANDARD = re.compile(
    r"\b(?:сравн\w*|проанализ\w*|анализ\w*|аудит\w*|проверь|"
    r"диверсифик\w*|ребаланс\w*|продать|продаж\w*|купить|покупк\w*|"
    r"реинвест\w*|отчетност\w*|рекоменд\w*|распредел\w*|"
    r"compare|analy[sz]\w*|audit|rebalance|diversif\w*|buy|sell|allocate|recommend\w*)\b",
    re.IGNORECASE,
)
ANALYTIC_REQUEST = re.compile(r"\b(?:сравни\w*|проанализ\w*|проверь|оцени\w*|рассчита\w*|compare|analy[sz]e|assess|calculate|audit)\b", re.IGNORECASE)
LIMITS = {AnalysisTier.FAST: 600, AnalysisTier.STANDARD: 1200, AnalysisTier.PREMIUM: 1600}
TIER_ORDER = {AnalysisTier.FAST: 0, AnalysisTier.STANDARD: 1, AnalysisTier.PREMIUM: 2}


class ChatPolicyError(ValueError):
    def __init__(self, code: str, user_message: str):
        super().__init__(code)
        self.code = code
        self.user_message = user_message


@dataclass(frozen=True)
class ChatPlan:
    tier: AnalysisTier
    required_tier: AnalysisTier
    max_output_tokens: int
    reason: str
    policy_version: str = POLICY_VERSION

    def metadata(self) -> dict:
        return {"selected_tier": self.tier.value, "required_tier": self.required_tier.value,
                "max_output_tokens": self.max_output_tokens, "routing_reason": self.reason,
                "policy_version": self.policy_version, "classification_method": "deterministic_rules",
                "requires_cost_confirmation": self.tier is AnalysisTier.PREMIUM}


def normalized(text: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFKC", text)
                            if unicodedata.category(c) != "Cf").casefold().replace("ё", "е").split())


def is_introduction(text: str) -> bool:
    """Exact standalone greetings only; never strip an attached financial task."""
    return normalized(text).rstrip("?.! ") in INTRODUCTION


def response_budget(max_output_tokens: int) -> dict:
    """Prompt targets leave room for JSON/evidence inside the unchanged cap.

    Character counts are writing targets, not a claim about provider tokenization.
    The paid request and reservation still use the existing hard token limit.
    """
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 4000:
        raise ValueError("chat_output_budget_invalid")
    if max_output_tokens <= LIMITS[AnalysisTier.FAST]:
        answer, claims, uncertainties = 350, 2, 1
    elif max_output_tokens <= LIMITS[AnalysisTier.STANDARD]:
        answer, claims, uncertainties = 700, 3, 2
    else:
        answer, claims, uncertainties = 1000, 4, 2
    return {"max_output_tokens": max_output_tokens, "answer_characters_target": answer,
            "claims_max": claims, "claim_characters_target": 90,
            "uncertainties_max": uncertainties, "uncertainty_characters_target": 100,
            "navigation_items_max": 2}


def _outside(text: str) -> bool:
    return bool(OUTSIDE.search(text) or UNRELATED_TASK.search(text) or RETAIL.search(text) or INJECTION.search(text))


def _financial_history(history: Sequence[str]) -> str | None:
    # Retain the complexity of the latest financial question, not model prose.
    # Do not cross an unrelated question or another user's conversation.
    for prior in reversed(history[-4:]):
        prior = normalized(prior[:8000])
        if _outside(prior):
            return None
        if FINANCE.search(prior):
            return prior
        if not _follow_up(prior):
            return None
    return None


def _required_tier(cleaned: str) -> AnalysisTier:
    parts = [part for part in re.split(r"[.!?;]+", cleaned) if part.strip()]
    if DEFINITION.search(cleaned) and not ANALYTIC_REQUEST.search(cleaned) and len(parts) == 1:
        return AnalysisTier.FAST
    if DEEP.search(cleaned):
        return AnalysisTier.PREMIUM
    if STANDARD.search(cleaned):
        return AnalysisTier.STANDARD
    return AnalysisTier.FAST


def _selected_tier(requested: str, required: AnalysisTier) -> AnalysisTier:
    if requested == "auto":
        return required
    try:
        selected = AnalysisTier(requested)
    except (ValueError, TypeError):
        raise ChatPolicyError("chat_tier_invalid", TIER_MESSAGE) from None
    if selected not in TIER_ORDER:
        raise ChatPolicyError("chat_tier_invalid", TIER_MESSAGE)
    if TIER_ORDER[selected] < TIER_ORDER[required]:
        raise ChatPolicyError("chat_tier_insufficient", TIER_MESSAGE)
    return selected


def plan_chat(text: str, requested_tier: str = "auto", *, history: Sequence[str] = (),
              verified_context: bool = False) -> ChatPlan:
    # verified_context is supplied only by the server after owner/broker checks;
    # it permits bounded clarification phrases, never an arbitrary new topic.
    if not isinstance(text, str) or not 1 <= len(text) <= 8000 or not text.strip():
        raise ChatPolicyError("chat_text_invalid", CLARIFY_MESSAGE)
    cleaned = normalized(text)
    if _outside(cleaned):
        raise ChatPolicyError("chat_outside_investment_scope", SCOPE_MESSAGE)
    prior = _financial_history(history)
    follow_up = _follow_up(cleaned)
    introduction = is_introduction(text)
    if not introduction and not FINANCE.search(cleaned) and not (follow_up and (verified_context is True or prior)):
        raise ChatPolicyError("chat_investment_scope_unclear", CLARIFY_MESSAGE)
    required = _required_tier(prior if follow_up and prior else cleaned)
    selected = _selected_tier(requested_tier, required)
    return ChatPlan(selected, required, LIMITS[selected],
                    "task_complexity" if requested_tier == "auto" else "explicit_user_tier")


