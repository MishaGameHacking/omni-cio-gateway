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
const displayContext = {window: {OMNICIO_I18N: I}, Intl, console};
vm.runInNewContext(readFileSync(join(__dirname, "../web/workspace.js"), "utf8"), displayContext);
displayContext.window.OmniUI.setLocale("en");
assert.equal(displayContext.window.OmniUI.navigation.find(([key]) => key === "events")[1], "Events");
assert.ok(displayContext.window.OmniUI.periods("portfolio", "1d").includes("1D"));
displayContext.window.OmniUI.setLocale("ru");
assert.equal(displayContext.window.OmniUI.navigation.find(([key]) => key === "events")[1], "События", "Labels must be evaluated in the current locale, not frozen at page startup");
assert.ok(displayContext.window.OmniUI.periods("portfolio", "1d").includes("1Д"));
for (const file of ["app.js", "workspace.js"]) {
  const code = readFileSync(join(__dirname, "../web/", file), "utf8");
  for (const match of code.matchAll(/\b[TH]\(("(?:\\.|[^"\\])*")/g)) {
    const key = JSON.parse(match[1]);
    assert.ok(I.has(key), `${file} has an authored UI message without a translation: ${key}`);
  }
}
console.log(`PASS i18n: ${I.keys().length} bilingual messages, all tabs, reversible explicit DOM hooks, private-data boundaries and escaped interpolation`);
