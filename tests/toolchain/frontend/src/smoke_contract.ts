export const TOOLCHAIN_SMOKE_LABEL = "Omni-CIO V10 toolchain smoke";

export function buildToolchainSmokeLabel(suffix: string): string {
  const normalized = suffix.trim();
  if (normalized.length === 0) {
    throw new Error("TOOLCHAIN_SMOKE_SUFFIX_EMPTY");
  }
  return `${TOOLCHAIN_SMOKE_LABEL} — ${normalized}`;
}
