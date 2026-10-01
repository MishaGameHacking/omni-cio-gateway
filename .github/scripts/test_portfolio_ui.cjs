// Synthetic owner-session acceptance; no credentials or external API calls.
"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");
const {chromium} = require("playwright");

const root = path.resolve(__dirname, "../..");
const analysis = JSON.parse(fs.readFileSync(path.join(__dirname, "portfolio-analysis.fixture.json"), "utf8"));

const timestamp = new Date().toISOString();
const fixture = {
  analysis, account_name: "Synthetic account", environment: "sandbox", refreshed_at: timestamp,
  sources: ["portfolio", "positions", "catalog"].map(id => ({
    id, name: "T-Invest: " + id, url: "https://developer.tbank.ru/invest/api/instruments-service",
    methods: ["Synthetic provider read"], retrieved_at: timestamp, status: "received",
  })),
};
let mode = "success";
let connected = true;
let calls = 0;
const server = http.createServer((request, response) => {
  const pathname = new URL(request.url, "http://localhost").pathname;
  const send = (body, status = 200, type = "application/json") => {
    response.writeHead(status, {"Content-Type": type});
    response.end(type === "application/json" ? JSON.stringify(body) : body);
  };
  if (pathname === "/") return send(fs.readFileSync(path.join(root, "web/index.html")), 200, "text/html");
  if (pathname === "/assets/app.js") return send(fs.readFileSync(path.join(root, "web/app.js")), 200, "text/javascript");
  if (pathname === "/assets/app.css") return send(fs.readFileSync(path.join(root, "web/app.css")), 200, "text/css");
  if (pathname === "/version.js") return send('window.OMNICIO_RELEASE={version:"0.6.0",build:"synthetic"};', 200, "text/javascript");
  if (pathname === "/api/me") return send({public_id:"000000001"});
  if (pathname === "/api/broker/tbank" && request.method === "DELETE") {
    connected = false;
    return send({});
  }
  if (pathname === "/api/broker/tbank") return send({connected, environment:"sandbox", account_name:"Synthetic account"});
  if (pathname === "/api/broker/tbank/operations") return send({items:[],has_next:false});
  if (pathname === "/api/broker/tbank/analysis") {
    calls++;
    if (mode === "error") return send({detail:"unavailable"}, 503);
    if (mode === "empty") return send({...fixture, analysis:{...analysis,
      securities:[], sectors:[], classes:[], security_count:0,
      sector_coverage_percent:null, rub_cash_unblocked:null}});
    return send(fixture);
  }
  if (pathname.endsWith("/stream")) return send('event: status\ndata: {"state":"unavailable"}\n\n', 200, "text/event-stream");
  return send({detail:"synthetic unavailable"}, 503);
});

async function checkViewport(browser, origin, label, viewport) {
  connected = true;
  mode = "success";
  const page = await browser.newPage({viewport});
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(origin);
  await page.locator("#profile-panel").waitFor({state:"visible"});
  await page.waitForFunction(() =>
    document.querySelector("#top-connection-text").textContent === "T-Invest подключён");
  const nav = label === "mobile" ? '[data-mobile-view="decisions"]' : '[data-view="decisions"]';
  await page.locator(nav).click();
  await page.locator("#analysis-content").waitFor({state:"visible"});
  assert.equal(await page.locator("#analysis-cash").innerText(), "80\u00a0₽");
  assert.equal(await page.locator("#analysis-securities tr").count(), 2);
  assert.equal(await page.locator("#analysis-securities img").count(), 0);
  assert.equal(await page.locator("#analysis-observations img").count(), 0);
  assert.match(await page.locator("#analysis-status").innerText(), /Песочница/);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  mode = "empty";
  await page.locator("#analysis-refresh").click();
  await page.waitForFunction(() => document.querySelector("#analysis-count").textContent === "0");
  assert.equal(await page.locator("#analysis-cash").innerText(), "Не подтверждены");
  mode = "error";
  await page.locator("#analysis-refresh").click();
  await page.waitForFunction(() => document.querySelector("#analysis-content").classList.contains("hidden"));
  assert.match(await page.locator("#analysis-status").innerText(), /не получен/);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({label, success:true, bodyOverflow:false}));
  await page.close();
}

(async () => {
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  const origin = "http://127.0.0.1:" + address.port;
  const browser = await chromium.launch({headless:true});
  try {
    await checkViewport(browser, origin, "desktop", {width:1440,height:1000});
    await checkViewport(browser, origin, "mobile", {width:390,height:844});
    assert.equal(calls, 6);
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
}).finally(() => server.close());
