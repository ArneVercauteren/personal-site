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
 * Compact money for chart axes, e.g. 146638651 -> "$147M", 940580 -> "$941K".
 * A full-precision `money()` label (e.g. "$146,638,651") overflows a narrow
 * y-axis and gets clipped; the compact form keeps the axis legible at any
 * magnitude. Tooltips still use `money()` for the exact figure.
 */
export function compactMoney(value: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

/**
 * Adaptive x-axis date label for an equity curve, chosen by how many days the
 * visible window spans. A multi-year curve labelled "MMM YY" reads ambiguously
 * ("Apr 01" looks like April 1st, not April 2001), so wide spans collapse to the
 * year alone and medium spans mark the year with an apostrophe.
 *   span > ~2y   -> "2001"
 *   span > ~4mo  -> "Apr '01"
 *   else         -> "Apr 3"
 */
export function axisDate(iso: string, spanDays: number): string {
  const d = new Date(iso + "T00:00:00Z");
  if (spanDays > 730) {
    return String(d.getUTCFullYear());
  }
  const month = d.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" });
  if (spanDays > 120) {
    return `${month} '${String(d.getUTCFullYear()).slice(-2)}`;
  }
  return `${month} ${d.getUTCDate()}`;
}

/** Whole days between two ISO dates (YYYY-MM-DD), order-independent. */
export function spanDays(fromIso: string, toIso: string): number {
  const a = new Date(fromIso + "T00:00:00Z").getTime();
  const b = new Date(toIso + "T00:00:00Z").getTime();
  return Math.abs(b - a) / 86_400_000;
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

/**
 * Normalize a date string the Astralanx exporter may emit with a time suffix
 * ("2008-11-20 00:00:00") down to the bare ISO day ("2008-11-20"), which every
 * other helper here expects. Pass-through for already-bare dates.
 */
export function dateOnly(value: string): string {
  return value.slice(0, 10);
}

/** ISO date (YYYY-MM-DD) -> "Jun 1, 2026". */
export function shortDate(iso: string): string {
  const d = new Date(dateOnly(iso) + "T00:00:00Z");
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
