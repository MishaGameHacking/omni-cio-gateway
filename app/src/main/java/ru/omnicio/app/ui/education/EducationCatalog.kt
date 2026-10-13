package ru.omnicio.app.ui.education

import ru.omnicio.app.ui.spectrum.SpectrumSymbol

enum class EducationCategory(val title: String) {
    START("Старт"),
    INSTRUMENTS("Инструменты"),
    PORTFOLIO("Портфель"),
    NEWS("Новости"),
    SAFETY("Безопасность"),
}

data class EducationSource(
    val organization: String,
    val title: String,
    val url: String,
)

data class EducationLesson(
    val id: String,
    val category: EducationCategory,
    val title: String,
    val subtitle: String,
    val minutes: Int,
    val symbol: SpectrumSymbol,
    val explanation: String,
    val checkpoints: List<String>,
    val sources: List<EducationSource>,
)

/**
 * Original educational copy. Sources are links for deeper study, not copied lesson text.
 * Lessons explain mechanics and risks; they never promise returns or issue a trade order.
 */
object EducationCatalog {
    private val moexBeginner = EducationSource(
        organization = "Школа Московской биржи",
        title = "Курсы для начинающих инвесторов",
        url = "https://school.moex.com/courses/level/beginner",
    )
    private val moexStart = EducationSource(
        organization = "Школа Московской биржи",
        title = "С чего начать инвестиции — пошаговая инструкция",
        url = "https://school.moex.com/articles/s-chego-nachat-investicii-poshagovaya-instrukciya",
    )
    private val moexShares = EducationSource(
        organization = "Школа Московской биржи",
        title = "Инвестиции в акции: механика, расчёт и риски",
        url = "https://school.moex.com/articles/investicii-v-akcii-dlya-nachinayushchih-mekhanika-raschet-riski",
    )
    private val investorDiversification = EducationSource(
        organization = "Investor.gov",
        title = "Asset Allocation and Diversification",
        url = "https://www.investor.gov/introduction-investing/getting-started/asset-allocation",
    )
    private val investorRatings = EducationSource(
        organization = "Investor.gov",
        title = "The ABCs of Credit Ratings",
        url = "https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/updated-8",
    )
    private val financialCulture = EducationSource(
        organization = "Банк России",
        title = "Финансовая культура",
        url = "https://fincult.info/",
    )
    private val cbrRatings = EducationSource(
        organization = "Банк России",
        title = "Решения о кредитных рейтингах",
        url = "https://cbr.ru/finm_infrastructure/ra/rsd/",
    )

    val lessons: List<EducationLesson> = listOf(
        EducationLesson(
            id = "start-plan",
            category = EducationCategory.START,
            title = "Сначала цель, срок и резерв",
            subtitle = "Почему покупка бумаги — не первый шаг",
            minutes = 6,
            symbol = SpectrumSymbol.Analyst,
            explanation = "Инвестиционный план начинается с цели, срока и суммы, которая не понадобится на текущие расходы. Денежный резерв нужен, чтобы не продавать активы в неудобный момент из-за срочной траты.",
            checkpoints = listOf(
                "Запишите цель и дату, когда деньги могут понадобиться.",
                "Отделите резерв от инвестиционного капитала.",
                "Определите допустимую временную просадку в рублях, а не только в процентах.",
                "Не принимайте прошлую доходность за обещание будущей.",
            ),
            sources = listOf(moexStart, financialCulture),
        ),
        EducationLesson(
            id = "market-mechanics",
            category = EducationCategory.START,
            title = "Как устроена сделка на бирже",
            subtitle = "Инвестор, брокер, биржа, депозитарий и эмитент",
            minutes = 7,
            symbol = SpectrumSymbol.Sources,
            explanation = "Приложение брокера передаёт поручение, биржа сопоставляет заявки, а права на бумаги учитывает депозитарная система. Итог инвестора складывается из изменения цены и выплат, а комиссии и налоги уменьшают результат.",
            checkpoints = listOf(
                "Лимитная заявка задаёт максимальную цену покупки или минимальную цену продажи.",
                "Рыночная цена может измениться между просмотром и исполнением.",
                "Владение бумагой и красивый график в приложении — не одно и то же.",
                "Проверяйте комиссию, налоги, валюту расчётов и режим торгов.",
            ),
            sources = listOf(moexShares),
        ),
        EducationLesson(
            id = "asset-types",
            category = EducationCategory.INSTRUMENTS,
            title = "Акции, облигации, фонды и деньги",
            subtitle = "Что именно покупает инвестор",
            minutes = 9,
            symbol = SpectrumSymbol.Allocation,
            explanation = "Акция даёт долю в бизнесе, облигация — требование возврата долга, фонд объединяет набор активов, а денежные инструменты помогают хранить резерв. У каждого типа свои источники результата и свои риски.",
            checkpoints = listOf(
                "Акция зависит от бизнеса, оценки рынка и ожиданий.",
                "Облигация зависит от ставки, срока, ликвидности и способности заёмщика платить.",
                "Фонд может быть узким и поэтому не всегда означает хорошую диверсификацию.",
                "Высокая обещанная доходность обычно означает дополнительный риск, а не бесплатную прибыль.",
            ),
            sources = listOf(moexShares, investorDiversification),
        ),
        EducationLesson(
            id = "diversification",
            category = EducationCategory.PORTFOLIO,
            title = "Диверсификация без иллюзий",
            subtitle = "Разные активы, компании, отрасли, валюты и риски",
            minutes = 10,
            symbol = SpectrumSymbol.Portfolio,
            explanation = "Диверсификация уменьшает зависимость от одного сценария. Недостаточно купить несколько бумаг: они могут принадлежать одной группе, зависеть от одной отрасли, ставки, валюты или цены сырья.",
            checkpoints = listOf(
                "Смотрите на долю экономической группы, а не только на количество тикеров.",
                "Проверяйте крупнейшие позиции фондов, чтобы не дублировать один риск.",
                "Сравнивайте текущую структуру с целевой, связанной с вашим сроком и риском.",
                "Балансировка не обязана означать продажу: иногда достаточно направлять новые деньги в недостающие части.",
            ),
            sources = listOf(investorDiversification),
        ),
        EducationLesson(
            id = "credit-ratings",
            category = EducationCategory.PORTFOLIO,
            title = "Кредитный рейтинг: полезный сигнал, не гарантия",
            subtitle = "Как читать рейтинг облигации и эмитента",
            minutes = 8,
            symbol = SpectrumSymbol.Risk,
            explanation = "Кредитный рейтинг оценивает относительный кредитный риск на определённую дату. Он может меняться, использует шкалу конкретного агентства и не описывает рыночный, валютный или ликвидный риск.",
            checkpoints = listOf(
                "Не смешивайте разные агентства и национальные/международные шкалы как одинаковые числа.",
                "Проверяйте объект рейтинга: выпуск, эмитент или поручитель.",
                "Учитывайте дату, прогноз, статус пересмотра и отзыв рейтинга.",
                "Не покупайте низкорейтинговый долг только ради формального разнообразия рейтингов.",
            ),
            sources = listOf(investorRatings, cbrRatings),
        ),
        EducationLesson(
            id = "news-impact",
            category = EducationCategory.NEWS,
            title = "Как новости двигают рынок",
            subtitle = "Не заголовок, а изменение ожиданий",
            minutes = 11,
            symbol = SpectrumSymbol.Pulse,
            explanation = "Цена часто реагирует не на сам факт новости, а на разницу между фактом и тем, что рынок уже ожидал. Влияние проходит через будущую прибыль, ставку дисконтирования, валюту, сырьё, доступ к капиталу и общий спрос на риск.",
            checkpoints = listOf(
                "Отделите официальный факт от мнения, слуха и пересказа.",
                "Проверьте дату, первоисточник и было ли событие ожидаемым.",
                "Опишите путь влияния: событие → выручка/расходы/ставка/валюта → компания → портфель.",
                "Оцените срок действия: часы, квартал или несколько лет.",
                "Не делайте вывод по одному заголовку без масштаба и базы сравнения.",
            ),
            sources = listOf(financialCulture, moexShares),
        ),
        EducationLesson(
            id = "statements",
            category = EducationCategory.INSTRUMENTS,
            title = "Финансовая отчётность простыми словами",
            subtitle = "Выручка, прибыль, долг и денежный поток",
            minutes = 12,
            symbol = SpectrumSymbol.Analyst,
            explanation = "Отчётность помогает понять, откуда компания получает деньги, сколько тратит, сколько должна и превращается ли бухгалтерская прибыль в денежный поток. Одно отношение или один квартал не дают полной картины.",
            checkpoints = listOf(
                "Сравнивайте несколько периодов и объясняйте причину изменений.",
                "Смотрите на операционный денежный поток, долг и сроки его погашения.",
                "Отделяйте разовые доходы от устойчивого бизнеса.",
                "Не применяйте одинаковые коэффициенты к промышленной компании, банку и страховщику.",
            ),
            sources = listOf(moexShares),
        ),
        EducationLesson(
            id = "behavior",
            category = EducationCategory.SAFETY,
            title = "Психология инвестора и пауза перед решением",
            subtitle = "Страх, FOMO, подтверждение своего мнения и эффект недавнего",
            minutes = 8,
            symbol = SpectrumSymbol.Messages,
            explanation = "Даже правильные данные не защищают от импульсивного решения. Страх пропустить рост, желание срочно вернуть убыток, поиск только удобных аргументов и перенос недавнего движения в будущее могут нарушить заранее выбранный план.",
            checkpoints = listOf(
                "Запишите причину действия до открытия карточки покупки или продажи.",
                "Сравните решение с целью, сроком и допустимой долей позиции.",
                "Найдите факт, который противоречит вашему текущему мнению.",
                "Для несрочного решения используйте паузу и повторную проверку источников.",
                "Не увеличивайте риск только ради попытки быстро отыграть прошлый убыток.",
            ),
            sources = listOf(moexBeginner, financialCulture),
        ),
        EducationLesson(
            id = "fraud-and-hype",
            category = EducationCategory.SAFETY,
            title = "Мошенничество, хайп и обещания без риска",
            subtitle = "Как остановиться до перевода денег",
            minutes = 7,
            symbol = SpectrumSymbol.Risk,
            explanation = "Срочность, гарантированная высокая доходность, закрытый канал, просьба установить неизвестное приложение или перевести деньги на чужой кошелёк — повод остановиться и проверить организацию по официальным источникам.",
            checkpoints = listOf(
                "Не сообщайте коды, пароли, seed-фразы и токены доступа.",
                "Проверяйте лицензию и адрес организации независимо от рекламной ссылки.",
                "Не принимайте скриншоты чужой прибыли за доказательство стратегии.",
                "Никто не может гарантировать рыночную доходность без риска потерь.",
            ),
            sources = listOf(financialCulture),
        ),
    )
}
