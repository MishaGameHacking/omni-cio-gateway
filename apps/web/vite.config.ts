import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const gitSha = process.env.GITHUB_SHA?.trim() || "local";
const webVersion = "0.17.0-wp17";

export default defineConfig({
  plugins: [react()],
  define: {
    __OMNI_WEB_VERSION__: JSON.stringify(webVersion),
    __OMNI_WEB_BUILD_SHA__: JSON.stringify(gitSha),
  },
  build: {
    sourcemap: true,
  },
});