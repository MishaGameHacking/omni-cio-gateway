import type { SystemStatusView } from "./system-contracts";

export async function readSystemStatus(): Promise<SystemStatusView> {
  const response = await fetch("/api/v10/web/system-status", {
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`WEB_SYSTEM_API_${response.status}`);
  }
  return (await response.json()) as SystemStatusView;
}
