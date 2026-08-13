const DECIMAL_TEXT = /^([+-]?)(\d+)(?:\.(\d+))?$/;

function incrementUnsignedDigits(value: string): string {
  const digits = value.split("");
  for (let index = digits.length - 1; index >= 0; index -= 1) {
    const digit = digits[index];
    if (digit === undefined) continue;
    if (digit !== "9") {
      digits[index] = String.fromCharCode(digit.charCodeAt(0) + 1);
      return digits.join("");
    }
    digits[index] = "0";
  }
  return `1${digits.join("")}`;
}

export function formatDecimal(
  value: string | null | undefined,
  maximumFractionDigits = 2,
): string {
  if (value === null || value === undefined || value === "") return "—";
  const match = DECIMAL_TEXT.exec(value.trim());
  if (!match) return value;

  const sign = match[1] ?? "";
  let integer = (match[2] ?? "0").replace(/^0+(?=\d)/, "");
  let fraction = match[3] ?? "";
  const maximum = Number.isFinite(maximumFractionDigits)
    ? Math.max(0, Math.trunc(maximumFractionDigits))
    : fraction.length;

  if (fraction.length > maximum) {
    const roundingDigit = fraction[maximum] ?? "0";
    let kept = fraction.slice(0, maximum);
    if (roundingDigit >= "5") {
      const incremented = incrementUnsignedDigits(`${integer}${kept}`);
      if (maximum === 0) {
        integer = incremented;
        kept = "";
      } else {
        const padded = incremented.padStart(maximum + 1, "0");
        integer = padded.slice(0, -maximum);
        kept = padded.slice(-maximum);
      }
    }
    fraction = kept;
  }

  fraction = fraction.replace(/0+$/, "");
  const groupedInteger = integer.replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0");
  return `${sign}${groupedInteger}${fraction ? `,${fraction}` : ""}`;
}
