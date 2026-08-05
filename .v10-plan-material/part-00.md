**OMNI-CIO V10**

**Personal Autonomous Investment Platform**

**Канонический Master Plan разработки от A до Я**

**Статус: DRAFT / разработка не начата**

Базовая версия: Omni-CIO v9.0.0 (завершена и защищена как reference/rollback)

Дата формирования плана: 05.08.2026

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Назначение документа<br />
</strong>Этот PDF является рабочей программой для будущей автономной разработки V10 через GitHub. Он задаёт порядок работ, границы полномочий, критерии завершения, проверки и правила перехода между этапами. Пока владелец не даст отдельную команду начать V10, никакие изменения V9, GitHub, ноутбука, Telegram, сайта или торгового контура по этому плану не выполняются.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# 0. Управление документом и статус программы

- Источник текущей базовой архитектуры: accepted main репозитория Misha2304/omni-cio-gateway.

- V9 имеет статус COMPLETE; новый feature work требует отдельной owner-approved программы согласно AGENTS.md.

- V10 не переписывает финансовые engines без доказанной необходимости: Research, Credit, Risk, Strategy, Optimizer, Immutable Plans, Safe Execution, Watchtower и Decision Journal наследуются из V9.

- Этот документ является программой разработки, а не доказательством реализации функций. Любая capability считается реализованной только после кода, тестов, CI, security gate и требуемой owner acceptance.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Ключевой принцип<br />
</strong>Сначала безопасность и воспроизводимость. Затем инфраструктура. Затем Core. Затем сайт. Затем Telegram. Затем Research/AI. Затем Guardian. И только после длительного Shadow Mode - персональное исполнение реальных сделок.</th>
</tr>
</thead>
<tbody>
</tbody>
</table>

# Содержание программы

- 1\. Цель V10 и целевая архитектура

- 2\. Неизменяемые инженерные правила

- 3\. Модель прогресса и Definition of Done

- BLOCK A - Архитектура и защита V9

- BLOCK B - GitHub, зависимости и CI/CD

- BLOCK C - Lenovo Omni-CIO Node

- BLOCK D - V10 Core и данные

- BLOCK E - Omni-CIO Web Platform

- BLOCK F - Telegram и связь с Web

- BLOCK G - Research + Local AI

- BLOCK H - Guardian / Watchtower Loop

- BLOCK I - Personal Real Execution

- BLOCK J - Системная интеграция, hardening и release

- 14\. Сквозная стратегия тестирования

- 15\. Работа с ошибками и инцидентами

- 16\. Правила моей будущей работы через GitHub

- 17\. Что намеренно НЕ входит в V10

- 18\. Минимальное участие владельца

- 19\. Финальный Definition of Done V10

- 20\. Реестр внешних технических ориентиров и источников

# 1. Цель V10 и целевая архитектура

**Главная цель:** вынести Omni-CIO из обязательной зависимости от Custom GPT и превратить готовый V9 в самостоятельную персональную инвестиционную операционную систему, работающую 24/7 на постоянно включённом Lenovo, управляемую через GitHub, с единым сайтом, Telegram-оповещениями и опциональным локальным AI Researcher.

- GitHub - Control Plane и долговременная память разработки: код, архитектура, тесты, зависимости, releases, runbooks и recovery.

- Lenovo - основной Personal Omni-CIO Node 24/7: runtime, DB, Watchtower, Web, Telegram, Research worker и локальный AI при необходимости.

- Omni-CIO Core - единое финансовое ядро V9/V10, не зависящее от конкретного пользовательского интерфейса.

- Web - главный кабинет владельца: портфель, Watchtower, Research, Risk, Decisions, Plans, Execution, Journal, System Health.

- Telegram - тревожная система и быстрый вход на правильную страницу Web; не отдельный финансовый мозг.

- Local AI - сменный Research Intelligence Layer. Его отсутствие не ломает Core и не даёт модели прямых прав на брокерские записи.

- T-Invest - источник реального портфеля/рынка и отдельный защищённый execution contour для OWNER.

PRIVATE GITHUB  
\|  
v  
LENOVO OMNI-CIO NODE 24/7  
\|-- Core (Portfolio / Risk / Optimizer / Watchtower / Plans / Journal)  
\|-- PostgreSQL / Local State  
\|-- Research Collector / Optional AI  
\|-- Web API + Web App  
\|-- Telegram Bot  
\`-- T-Invest read + isolated OWNER execution

# 2. Неизменяемые инженерные правила

1.  V9 не уничтожается и остаётся защищённой reference/rollback версией до полного V10 acceptance.

2.  Один репозиторий, один Omni-CIO Core, один основной Web App. Запрещено плодить параллельные competing stacks без amendment к программе.

3.  Real READ token, Sandbox token и Real TRADING token всегда разделены. Trading token не является fallback для чтения и не попадает в GitHub.

4.  AI не имеет прямого PostOrder/execute права. AI создаёт структурированное research/evidence; финансовые ограничения, sizing и execution authority находятся в детерминированном Core.

5.  Каждый Real plan immutable. Изменение хотя бы одной существенной части отменяет старое подтверждение.

6.  Возможная отправка заявки при сетевой неопределённости не повторяется автоматически: только reconciliation.

7.  `submitted` никогда не приравнивается к `filled` без брокерского доказательства.

8.  Любая внешняя информация имеет provenance, published_at/retrieved_at, freshness и identity binding.

9.  Любой компонент обязан fail closed, если не хватает данных для безопасного сильного вывода или Real action.

10. Новая технология выбирается не по принципу latest=best, а после official-doc review, security/license/maintenance/Windows compatibility и доказанного преимущества.

11. Public/multi-user архитектура может быть подготовлена на уровне моделей, но не активируется в V10 Personal.

# 3. Модель прогресса и Definition of Done

| **Блок** | **Назначение**                 | **Вес** | **Статус при старте** |
|----------|--------------------------------|---------|-----------------------|
| A        | Архитектура и защита V9        | 5%      | NOT STARTED           |
| B        | GitHub, зависимости и CI/CD    | 10%     | NOT STARTED           |
| C        | Lenovo Node / инфраструктура   | 15%     | NOT STARTED           |
| D        | V10 Core и данные              | 15%     | NOT STARTED           |
| E        | Web Platform                   | 15%     | NOT STARTED           |
| F        | Telegram                       | 8%      | NOT STARTED           |
| G        | Research + Local AI            | 12%     | NOT STARTED           |
| H        | Guardian / Watchtower Loop     | 8%      | NOT STARTED           |
| I        | Personal Real Execution        | 7%      | NOT STARTED           |
| J        | Hardening / Recovery / Release | 5%      | NOT STARTED           |
