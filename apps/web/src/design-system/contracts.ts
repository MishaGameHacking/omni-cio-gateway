export const operationalStates = [
  "READY",
  "PARTIAL",
  "STALE",
  "DEGRADED",
  "BLOCKED",
  "ERROR",
  "OFFLINE",
  "RECOVERING",
  "OWNER_ACTION_REQUIRED",
] as const;

export type OperationalState = (typeof operationalStates)[number];

export const riskSeverities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"] as const;
export type RiskSeverity = (typeof riskSeverities)[number];

export const viewportMatrix = [360, 768, 1440] as const;

export function isOperationalState(value: string): value is OperationalState {
  return operationalStates.includes(value as OperationalState);
}
