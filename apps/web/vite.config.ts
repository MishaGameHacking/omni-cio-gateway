import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import packageJson from "./package.json" with { type: "json" };

const buildSha =
  process.env.OMNI_V10_RELEASE_SHA ??
  process.env.GITHUB_SHA ??
  "local-dev";

export default defineConfig({
  plugins: [react()],
  define: {
    __OMNI_WEB_VERSION__: JSON.stringify(packageJson.version),
    __OMNI_WEB_BUILD_SHA__: JSON.stringify(buildSha),
  },
  build: {
    sourcemap: false,
    target: "es2022",
  },
  server: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
    strictPort: true,
  },
});
