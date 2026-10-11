/* Public-site browser acceptance. Fixtures never enter the deployable assets. */
"use strict";
const assert = require("node:assert/strict");
const {createServer} = require("node:http");
const {readFileSync, writeFileSync, existsSync, mkdirSync, mkdtempSync, rmSync} = require("node:fs");
const {join, resolve, extname} = require("node:path");
const {tmpdir} = require("node:os");
const {spawn, spawnSync} = require("node:child_process");
const root = resolve(__dirname, "..");
const rendered = spawnSync(process.env.OMNICIO_PYTHON || "python", ["-c", "import json;from pathlib import Path;from omnicio.web_assets import render_web_assets;print(json.dumps(render_web_assets(Path('web'),'browser-test')))"], {cwd:root,env:{...process.env,PYTHONPATH:join(root,"src")},encoding:"utf8"});
assert.equal(rendered.status, 0, rendered.stderr);
const assets = JSON.parse(rendered.stdout);
const artifacts = join(root,"artifacts","frontend");
mkdirSync(artifacts,{recursive:true});
let release = {status:"unpublished"};
let unavailable = false;
const requests = [];
const server = createServer((request,response) => {
  const path = new URL(request.url,"http://localhost").pathname;
  requests.push({path,method:request.method,cookie:request.headers.cookie});
  const types = {".html":"text/html", ".js":"text/javascript", ".css":"text/css", ".json":"application/json", ".webmanifest":"application/manifest+json", ".png":"image/png"};
  response.setHeader("Content-Type",types[extname(path)] || "text/html");
  response.setHeader("Cache-Control","no-store");
  response.setHeader("Content-Security-Policy","default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
  if(path === "/downloads/android.json") { response.statusCode = unavailable ? 503 : 200; response.end(JSON.stringify(release)); return; }
  if(path === "/assets/brand/omnicio-logo.png") {response.end(readFileSync(join(root,"assets/brand/omnicio-logo.png")));return;}
  const body = assets[path === "/" ? "index.html" : path.slice(1)];
  response.statusCode = body === undefined ? 404 : 200;
  response.end(body ?? "Not found");
});
const delay = ms => new Promise(done=>setTimeout(done,ms));
async function until(read,label) { for(let i=0;i<150;i++){if(await read())return;await delay(100);}throw Error("Timeout: "+label); }
async function protocol(url) {
  const socket = new WebSocket(url);const pending=new Map();let id=0;
  await new Promise((done,reject)=>{socket.addEventListener("open",done,{once:true});socket.addEventListener("error",reject,{once:true});});
  socket.addEventListener("message",({data})=>{const result=JSON.parse(data),p=pending.get(result.id);if(!p)return;pending.delete(result.id);clearTimeout(p.timer);if(result.error)p.reject(Error(JSON.stringify(result.error)));else p.done(result.result);});
  return {close:()=>socket.close(),send(method,params={},sessionId){return new Promise((done,reject)=>{const n=++id;const timer=setTimeout(()=>{pending.delete(n);reject(Error(method+" timeout"));},15000);pending.set(n,{done,reject,timer});socket.send(JSON.stringify({id:n,method,params,sessionId}));});}};
}
async function run(base) {
  const executable=[process.env.OMNICIO_TEST_BROWSER,"/usr/bin/google-chrome","/usr/bin/chromium","C:/Program Files/Google/Chrome/Application/chrome.exe","C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe","C:/Program Files/Microsoft/Edge/Application/msedge.exe"].filter(Boolean).find(existsSync);
  assert.ok(executable,"A real browser is required; set OMNICIO_TEST_BROWSER");
  const profile=mkdtempSync(join(tmpdir(),"omnicio-public-test-"));
  const child=spawn(executable,["--headless=new","--no-sandbox","--disable-dev-shm-usage","--disable-background-networking","--no-first-run","--remote-debugging-port=0",`--user-data-dir=${profile}`,"about:blank"],{stdio:["ignore","ignore","pipe"]});
  let websocket="",exited=false,client;
  child.stderr.on("data",chunk=>{const found=/DevTools listening on (ws:\/\/[^\s]+)/.exec(String(chunk));if(found)websocket=found[1];});
  child.on("exit",()=>{exited=true;});child.on("error",()=>{exited=true;});
  try {
    await until(()=>websocket||exited,"browser start");assert.ok(websocket);
    client=await protocol(websocket);
    const target=await client.send("Target.createTarget",{url:"about:blank"});
    const {sessionId}=await client.send("Target.attachToTarget",{targetId:target.targetId,flatten:true});
    const send=(method,params={})=>client.send(method,params,sessionId);
    const evaluate=async expression=>{const result=await send("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true});if(result.exceptionDetails)throw Error(result.exceptionDetails.exception?.description||result.exceptionDetails.text);return result.result.value;};
    await send("Page.enable");await send("Runtime.enable");
    await send("Page.addScriptToEvaluateOnNewDocument",{source:'window.__errors=[];addEventListener("error",e=>__errors.push(e.message));addEventListener("unhandledrejection",e=>__errors.push(String(e.reason)));addEventListener("securitypolicyviolation",e=>__errors.push(e.effectiveDirective));'});
    const wait=text=>until(()=>evaluate(text),text);
    const click=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
    for(const width of [1440,768,390,320]) {
      await send("Emulation.setDeviceMetricsOverride",{width,height:960,deviceScaleFactor:1,mobile:width<680});
      await send("Page.navigate",{url:base+"/?width="+width});
      await wait('document.readyState==="complete" && document.querySelector("#download-status")?.textContent.includes("Публичный выпуск")');
      assert.equal(await evaluate('document.querySelectorAll("form,input,textarea").length'),0,"No web account or personal data collection");
      assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth'),true,"No horizontal overflow at "+width);
      assert.deepEqual(await evaluate('window.__errors'),[]);
      await click('#tab-portfolio');assert.equal(await evaluate('document.querySelector("#panel-portfolio").hidden'),false);
      await evaluate('document.querySelector("#tab-portfolio").dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowRight",bubbles:true}))');
      assert.equal(await evaluate('document.activeElement.id'),"tab-assistant");
      assert.equal(await evaluate('document.querySelector("#panel-assistant").hidden'),false);
      await click('#tab-overview');
      await click('details summary');assert.equal(await evaluate('document.querySelector("details").open'),true);
      await click('details summary');
      assert.equal(await evaluate('document.querySelector("#apk-download").hasAttribute("href")'),false);
      const screen=await send("Page.captureScreenshot",{format:"png",captureBeyondViewport:true});
      writeFileSync(join(artifacts,`public-${width}.png`),Buffer.from(screen.data,"base64"));
      console.log("PASS public layout, tabs, keyboard, FAQ, unavailable release "+width+"px");
    }
    // Release errors must never retain a previously enabled download URL.
    release={status:"published",package:"ru.omnicio.app",version:"9.9.9",version_code:999,sha256:"a".repeat(64),certificate_sha256:"b".repeat(64),commit:"c".repeat(40),url:"/downloads/omnicio-9.9.9-"+"c".repeat(40)+".apk"};
    await click('#check-release');await wait('!document.querySelector("#apk-download").hidden');
    assert.equal(await evaluate('document.querySelector("#apk-download").getAttribute("href")'),release.url);
    for(const invalid of [{...release,url:"https://evil.example/app.apk"},{...release,package:"ru.omnicio.app.debug"},{...release,sha256:null}]) {
      release=invalid;await click('#check-release');await wait('!document.querySelector("#check-release").disabled');
      assert.equal(await evaluate('document.querySelector("#apk-download").hasAttribute("href")'),false);
      assert.equal(await evaluate('document.querySelector("#apk-download").hidden'),true);
    }
    unavailable=true;await click('#check-release');await wait('document.querySelector("#download-status").textContent.includes("Не удалось")');
    unavailable=false;release={status:"unpublished"};await click('#check-release');await wait('document.querySelector("#download-status").textContent.includes("Публичный выпуск")');
    await evaluate('caches.open("omnicio-public-obsolete");caches.open("unrelated-test-cache")');
    await evaluate('navigator.serviceWorker.register("/sw.js",{updateViaCache:"none"})');
    await until(()=>evaluate('(async()=>!(await caches.keys()).some(k=>k.startsWith("omnicio-")))()'),"Retire old cache");
    assert.equal(await evaluate('(async()=>(await caches.keys()).includes("unrelated-test-cache"))()'),true);
    assert.deepEqual(await evaluate('window.__errors'),[]);
    assert.equal(requests.some(r=>r.path.startsWith("/api/")||r.method!=="GET"),false,"No personal API, market or LLM traffic");
    assert.equal(requests.filter(r=>r.path==="/downloads/android.json").some(r=>r.cookie),false);
    writeFileSync(join(artifacts,"public-requests.json"),JSON.stringify(requests,null,2));
    console.log("PASS release rejection/recovery, PWA cache retirement and zero personal requests");
  } finally {
    if(client){try{await client.send("Browser.close");}catch{}client.close();}
    if(!exited)child.kill();
    await until(()=>exited,"browser exit");
    rmSync(profile,{recursive:true,force:true,maxRetries:5,retryDelay:200});
  }
}
(async()=>{await new Promise(done=>server.listen(0,"127.0.0.1",done));try{await run(`http://127.0.0.1:${server.address().port}`);}finally{server.close();}})().catch(error=>{console.error(error);process.exitCode=1;});
