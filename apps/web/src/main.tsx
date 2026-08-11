import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ApplicationShell } from "./app-shell/app-shell";
import { AppErrorBoundary } from "./app-shell/error-boundary";
import "./design-system/tokens.css";
import "./design-system/base.css";
import "./app-shell/app-shell.css";

const root = document.getElementById("root");
if (!root) throw new Error("WEB_ROOT_MISSING");

createRoot(root).render(
  <StrictMode>
    <AppErrorBoundary>
      <ApplicationShell />
    </AppErrorBoundary>
  </StrictMode>,
);