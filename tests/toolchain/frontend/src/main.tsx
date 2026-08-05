import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

function ToolchainSmoke(): JSX.Element {
  return <main>Omni-CIO V10 toolchain smoke</main>;
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
