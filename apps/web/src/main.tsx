import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { DesignSystemGallery } from "./design-system/gallery";
import "./design-system/tokens.css";
import "./design-system/base.css";

const root = document.getElementById("root");
if (!root) throw new Error("WEB_ROOT_MISSING");

createRoot(root).render(
  <StrictMode>
    <DesignSystemGallery />
  </StrictMode>,
);
