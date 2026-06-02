// Display formatting helpers. Numbers render in mono/tabular type on the site.

/** Format a fraction as a percentage, e.g. 0.081 -> "8.1%". */
export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

/** Signed percentage, e.g. 0.081 -> "+8.1%", -0.12 -> "-12.0%". */
export function signedPct(value: number, digits = 1): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${pct(value, digits)}`;
}

/** Format a money amount in a base currency, e.g. 100000 -> "$100,000". */
export function money(value: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

/**
 * Whole years from an ISO birth date (YYYY-MM-DD) to `now`.
 * Defaults to the current date — for statically rendered pages this is the
 * build-time date, so the age refreshes whenever the site is rebuilt.
 */
export function age(birthIso: string, now: Date = new Date()): number {
  const b = new Date(birthIso + "T00:00:00Z");
  let years = now.getUTCFullYear() - b.getUTCFullYear();
  const beforeBirthday =
    now.getUTCMonth() < b.getUTCMonth() ||
    (now.getUTCMonth() === b.getUTCMonth() &&
      now.getUTCDate() < b.getUTCDate());
  if (beforeBirthday) years -= 1;
  return years;
}

/** ISO date (YYYY-MM-DD) -> "Jun 1, 2026". */
export function shortDate(iso: string): string {
  const d = new Date(iso + "T00:00:00Z");
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
