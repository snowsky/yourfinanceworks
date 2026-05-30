// Money helpers that avoid binary-float drift.
//
// Summing amounts with `+`/reduce accumulates error (0.1 + 0.2 === 0.30000000000000004),
// which then renders as wrong figures in totals. sumMoney accumulates in integer cents;
// roundMoney/formatMoney round to 2dp for display.

/** Round a single amount to 2 decimal places. */
export function roundMoney(value: number): number {
  return Math.round((Number(value) + Number.EPSILON) * 100) / 100;
}

/** Sum amounts exactly by accumulating in integer cents (no float drift). */
export function sumMoney(values: Array<number | null | undefined>): number {
  const cents = values.reduce<number>(
    (acc, v) => acc + Math.round((Number(v) || 0) * 100),
    0,
  );
  return cents / 100;
}

/** Locale-aware 2dp formatting (thousands separators), drift- and toFixed-bug-free. */
export function formatMoney(value: number): string {
  return roundMoney(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
