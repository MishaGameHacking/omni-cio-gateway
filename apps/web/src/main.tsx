import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ApplicationShell } from "./app-shell/app-shell";
import { AppErrorBoundary } from "./app-shell/error-boundary";
import { DesignSystemGallery } from "./design-system/gallery";
import "./design-system/tokens.css";
import "./design-system/base.css";
import "./app-shell/app-shell.css";
import "./app-shell/portfolio-dashboard.css";
import "./app-shell/watchtower-incidents.css";
import "./app-shell/research-dossier.css";

const root = document.getElementById("root");
if (!root) throw new Error("WEB_ROOT_MISSING");

const wp16Gallery = new URLSearchParams(window.location.search).get("wp16-gallery") === "1";

createRoot(root).render(
  <StrictMode>
    <AppErrorBoundary>
      {wp16Gallery ? <DesignSystemGallery /> : <ApplicationShell />}
    </AppErrorBoundary>
  </StrictMode>,
);
