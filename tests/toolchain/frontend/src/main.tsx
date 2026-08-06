import { StrictMode, type ReactElement } from "react";
import { createRoot } from "react-dom/client";

import { buildToolchainSmokeLabel } from "./smoke_contract";

function ToolchainSmoke(): ReactElement {
  return <main>{buildToolchainSmokeLabel("WP3 protected")}</main>;
}

const root = document.getElementById("root");
if (root === null) {
  throw new Error("TOOLCHAIN_SMOKE_ROOT_MISSING");
}

createRoot(root).render(
  <StrictMode>
    <ToolchainSmoke />
  </StrictMode>,
);
