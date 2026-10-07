"use strict";

const assert = require("node:assert/strict");
const {readFileSync} = require("node:fs");
const {join} = require("node:path");
const vm = require("node:vm");
const I = require("../web/i18n.js");

assert.equal(I.getLocale(), "ru");
assert.equal(I.t("nav.events"), "События");
assert.equal(I.setLocale("en-US"), "en");
assert.equal(I.t("nav.events"), "Events");
assert.equal(I.t("События"), "Events", "Explicit authored literals share the semantic registry");
assert.equal(I.t("goals.active", {}, "ru"), "Активные цели", "The final authored override remains authoritative");
assert.equal(I.t("goals.active", {}, "en"), "Active goals");
assert.equal(I.t("Активная", {}, "en"), "Active", "The old status phrase remains a separate supported alias");
assert.equal(I.t("Ранее начатые исполнения", {}, "en"), "Previous executions");
assert.equal(I.t("Обновить приложение", {}, "en"), "Update app", "Shared phrases retain first-insertion fallback precedence");
assert.equal(I.t("pwa.apply", {}, "en"), "Update application", "A semantic key retains its own authored wording");
assert.equal(I.t("Ограничение", {}, "en"), "Constraint", "An explicit phrase key wins over a semantic fallback");
assert.equal(I.t("billing.limit", {}, "en"), "Limit");
for (const key of ["home", "portfolio", "market", "strategies", "assistant", "goals", "analytics", "events", "profile", "settings"]) {
  assert.notEqual(I.t(`nav.${key}`, {}, "en"), I.t(`nav.${key}`, {}, "ru"), "Each primary tab has a translation");
}
for (const key of I.keys()) {
  assert.ok(I.t(key, {}, "en").trim());
  assert.ok(I.t(key, {}, "ru").trim());
}
assert.equal(I.t("events.unread_count", {count: 115}), "Unread: 115");
assert.equal(I.t("events.unread_count", {count: "<img src=x onerror=alert(1)>"}), "Unread: <img src=x onerror=alert(1)>", "Text translator never silently changes input values");
assert.equal(I.html("events.unread_count", {count: "<img src=x onerror='bad'>"}), "Unread: &lt;img src=x onerror=&#39;bad&#39;&gt;", "HTML interpolation must escape the whole result");
assert.equal(I.t("unknown-authored-label"), "unknown-authored-label");
assert.equal(I.t("__proto__"), "__proto__");
assert.equal(I.t("constructor"), "constructor");
assert.equal(I.setLocale("de"), "ru", "Unsupported locale has a deterministic supported fallback");

const element = (attributes, text, {tagName = "SPAN", children = [], protectedContent = false} = {}) => ({
  attributes: {...attributes}, textContent: text, tagName, children,
  get dataset() { return Object.fromEntries(Object.entries(this.attributes).filter(([key]) => key.startsWith("data-")).map(([key,value]) => [key.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase()), value])); },
  getAttribute(key) { return this.attributes[key] || null; },
  setAttribute(key, value) { this.attributes[key] = value; },
  closest() { return protectedContent ? this : null; }
});
const menu = element({"data-i18n": "nav.portfolio"}, "Портфель");
const input = element({"data-i18n-placeholder": "nav.search", "data-i18n-aria-label": "nav.search"}, "", {tagName: "INPUT"});
input.value = "Моя цель с названием События";
const issuer = element({}, "Портфель");
const userTitle = element({"data-i18n": "nav.events"}, "События", {protectedContent: true});
const compound = element({"data-i18n": "action.refresh"}, "Обновить", {tagName: "BUTTON", children: [{tagName: "SVG"}]});
const root = {
  documentElement: {lang: "ru"},
  querySelectorAll() { return [menu, input, userTitle, compound]; }
};
I.apply(root, "en");
assert.equal(menu.textContent, "Portfolio");
assert.equal(input.attributes.placeholder, "Search");
assert.equal(input.attributes["aria-label"], "Search");
assert.equal(input.value, "Моя цель с названием События", "Switching locale must not edit form values");
assert.equal(userTitle.textContent, "События", "Private/source content remains original even if a marker is mistakenly inherited");
assert.equal(issuer.textContent, "Портфель", "Unmarked market/user values are never looked up by matching their text");
assert.equal(compound.children[0].tagName, "SVG");
assert.equal(compound.textContent, "Обновить", "A misplaced text marker must not destroy icon or control children");
assert.equal(root.documentElement.lang, "en");
I.apply(root, "ru");
assert.equal(menu.textContent, "Портфель", "Locale switching is reversible from canonical messages");
assert.equal(root.documentElement.lang, "ru");
const bootLabel = element({"data-i18n": "nav.events"}, "События");
const bootDocument = {
  documentElement: {dataset: {i18nDeviceLocale: ""}, lang: "ru"},
  readyState: "complete",
  querySelectorAll: () => [bootLabel]
};
const bootContext = {window: {}, document: bootDocument, navigator: {language: "en-US"}};
vm.runInNewContext(readFileSync(join(__dirname, "../web/i18n.js"), "utf8"), bootContext);
assert.equal(bootContext.window.OMNICIO_I18N.getLocale(), "en", "The device-locale API is ready synchronously");
assert.equal(bootDocument.documentElement.lang, "en");
assert.equal(bootLabel.textContent, "Events", "Initial rendering needs no additional asset or asynchronous catalog request");
const textNode = {nodeType: 3, data: "  Закрыть  "};
const iconButton = element({"data-i18n-text": '["Закрыть"]'}, "", {tagName: "BUTTON", children: [{tagName: "SVG"}]});
iconButton.childNodes = [{nodeType: 1, tagName: "SVG"}, textNode];
I.apply({querySelectorAll: () => [iconButton]}, "en");
assert.equal(textNode.data, "  Close  ");
assert.equal(iconButton.childNodes[0].tagName, "SVG", "Explicit shell text hooks preserve icons and DOM geometry");
I.apply({querySelectorAll: () => [iconButton]}, "ru");
assert.equal(textNode.data, "  Закрыть  ");
I.setLocale("en");
const originalPreset = {id: "balanced", title: "Сбалансированная", document: {allocation: {shares: 40}}};
assert.equal(I.preset(originalPreset).title, "Balanced");
assert.equal(originalPreset.title, "Сбалансированная", "Catalogue presentation must not mutate API records or saved strategy documents");
assert.strictEqual(I.preset(originalPreset).document, originalPreset.document);
assert.equal(I.preset({...originalPreset, title: "Моя стратегия пользователя"}).title, "Моя стратегия пользователя", "Matching an ID alone cannot authorize translation of arbitrary data");
assert.equal(I.preset({id: "unknown", title: "Сбалансированная"}).title, "Сбалансированная");
const source = {id: "buffett1989", title: "Berkshire Hathaway: письмо 1989 года", url: "https://www.berkshirehathaway.com/letters/1989.html"};
assert.equal(I.catalogSource(source).title, "Berkshire Hathaway: 1989 shareholder letter");
assert.equal(I.catalogSource(source).url, source.url);
const displayContext = {window: {OMNICIO_I18N: I}, Intl, console, URLSearchParams};
vm.runInNewContext(readFileSync(join(__dirname, "../web/workspace.js"), "utf8"), displayContext);
displayContext.window.OmniUI.setLocale("en");
assert.equal(displayContext.window.OmniUI.navigation.find(([key]) => key === "events")[1], "Events");
assert.ok(displayContext.window.OmniUI.periods("portfolio", "1d").includes("1D"));
displayContext.window.OmniUI.setLocale("ru");
assert.equal(displayContext.window.OmniUI.navigation.find(([key]) => key === "events")[1], "События", "Labels must be evaluated in the current locale, not frozen at page startup");
assert.ok(displayContext.window.OmniUI.periods("portfolio", "1d").includes("1Д"));
const U = displayContext.window.OmniUI;
for (const hash of ["#demo/market/reference?currency=CNY&reference_period=1y", "#account/portfolio/positions?assets=bond&sort=price&direction=-1", "#account/goals/plan?goal=00000000-0000-4000-8000-000000000001", "#public/features"]) {
  const route = U.parseRoute(hash);
  assert.equal(route.invalid, false, "A supported nested screen is a valid bookmark");
  assert.equal(U.routeHash(route), hash, "Mode, screen and controls survive a URL round trip");
}
assert.equal(U.parseRoute("#public-strategies").mode, "public");
assert.equal(U.parseRoute("#asset?uid=synthetic-a").uid, "synthetic-a");
assert.equal(U.parseRoute("#demo/unsupported").invalid, true);
assert.equal(U.parseRoute("#account/settings/unknown").invalid, true);
assert.equal(U.parseRoute("#public/features/unknown").invalid, true);
assert.equal(U.parseRoute("#account/home?user_id=other").user_id, undefined, "Navigation never accepts tenant authority fields");
for (const [hash, expected] of [
  ["#account/asset?uid=private-instrument", "#account/market"],
  ["#demo/search?q=private-search", "#demo/market"],
  ["#account/goals/edit?goal=private-goal", "#account/goals"],
  ["#account/goals/plan?goal=private-goal", "#account/goals"],
  ["#account/events/detail?event=private-event", "#account/events"],
  ["#demo/events/news?news=private-news", "#demo/events"],
  ["#account/strategies/detail?preset=private-preset", "#account/strategies"],
  ["#account/strategies/result?run=private-run", "#account/strategies"],
  ["#account/portfolio/positions?assets=bond&sort=price&overlay=private-overlay", "#account/portfolio/positions"],
  ["#public/features?q=private-search", "#public/features"],
  ["#account/market/reference/extra", "#public/welcome"],
  ["#account/unsupported", "#public/welcome"]
]) {
  const resumed = U.resumeRoute(U.parseRoute(hash));
  assert.equal(U.routeHash(resumed), expected, "Resume keeps a usable screen without saved identifiers or query text");
  assert.deepEqual(Array.from(Object.keys(resumed)).sort(), ["mode", "screen", "view"], "Stored resume metadata cannot contain q, uid, event, goal_id or overlay");
}
const scenario = U.chart([{month: 0, amount_rub: "100", target_rub: "200", contributions_rub: "0"}, {month: 12, amount_rub: "220", target_rub: "240", contributions_rub: "120"}], {timeKey: "month", valueKey: "amount_rub", xKind: "model_month", comparison: [{key: "target_rub", label: "Target"}, {key: "contributions_rub", label: "Contributions"}]});
assert.ok(scenario.includes("Месяц 12"));
assert.ok(!scenario.includes("1970"), "Model months cannot masquerade as observed calendar dates");
assert.ok(scenario.includes("chart-comparison-0"), "The scenario includes the numerical target series");
assert.ok(scenario.includes("chart-comparison-1"), "The scenario includes the numerical contributions series");
for (const file of ["app.js", "workspace.js"]) {
  const code = readFileSync(join(__dirname, "../web/", file), "utf8");
  for (const match of code.matchAll(/\b[TH]\(("(?:\\.|[^"\\])*")/g)) {
    const key = JSON.parse(match[1]);
    assert.ok(I.has(key), `${file} has an authored UI message without a translation: ${key}`);
  }
}
console.log(`PASS i18n: ${I.keys().length} bilingual messages, all tabs, reversible explicit DOM hooks, private-data boundaries and escaped interpolation`);
