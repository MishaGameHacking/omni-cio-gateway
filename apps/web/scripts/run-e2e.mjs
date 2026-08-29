import { spawn, spawnSync } from "node:child_process";
import { resolvePreviewEndpoint } from "./e2e-preview-endpoint.mjs";

const isWindows = process.platform === "win32";
const npmCommand = "npm";
const { port: previewPort, url: previewUrl } = resolvePreviewEndpoint();
const previewTimeoutMs = 30_000;
const browserTimeoutMs = 120_000;

function spawnNpm(args, options = {}) {
  return spawn(npmCommand, args, {
    ...options,
    shell: isWindows,
    windowsHide: true,
    env: { ...process.env, ...options.env },
  });
}

function killTree(child) {
  if (!child?.pid || child.exitCode !== null) return;
  if (isWindows) {
    spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      stdio: "ignore",
      windowsHide: true,
    });
    return;
  }
  child.kill("SIGTERM");
}

function tail(buffer, chunk) {
  const next = `${buffer}${chunk.toString("utf8")}`;
  return next.length <= 8_000 ? next : next.slice(-8_000);
}

async function waitForPreview(preview, output) {
  const deadline = Date.now() + previewTimeoutMs;
  while (Date.now() < deadline) {
    if (preview.exitCode !== null) {
      throw new Error(`Web preview exited before readiness with code ${preview.exitCode}.\n${output()}`);
    }
    try {
      const response = await fetch(previewUrl, { signal: AbortSignal.timeout(2_000) });
      if (response.ok) {
        console.log(`WP16 preview ready: ${previewUrl}`);
        return;
      }
    } catch {
      // Retry only inside the bounded readiness window.
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  throw new Error(`Web preview did not become ready within ${previewTimeoutMs}ms.\n${output()}`);
}

function waitForChild(child, timeoutMs) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      killTree(child);
      reject(new Error(`Browser evidence exceeded hard timeout ${timeoutMs}ms.`));
    }, timeoutMs);

    child.once("error", (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(error);
    });
    child.once("exit", (code, signal) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (signal) {
        reject(new Error(`Browser evidence exited by signal ${signal}.`));
        return;
      }
      resolve(code ?? 1);
    });
  });
}

let previewOutput = "";
const preview = spawnNpm(
  ["run", "preview", "--", "--host", "127.0.0.1", "--port", String(previewPort), "--strictPort"],
  { stdio: ["ignore", "pipe", "pipe"] },
);
preview.stdout.on("data", (chunk) => {
  previewOutput = tail(previewOutput, chunk);
});
preview.stderr.on("data", (chunk) => {
  previewOutput = tail(previewOutput, chunk);
});

try {
  await waitForPreview(preview, () => previewOutput);
  const browser = spawnNpm(["run", "e2e:browser"], {
    stdio: "inherit",
    env: { OMNI_WEB_PREVIEW_URL: previewUrl },
  });
  const code = await waitForChild(browser, browserTimeoutMs);
  if (code !== 0) {
    throw new Error(`Playwright browser evidence failed with exit code ${code}.`);
  }
  console.log("WP16 browser evidence completed successfully.");
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  process.exitCode = 1;
} finally {
  killTree(preview);
}
