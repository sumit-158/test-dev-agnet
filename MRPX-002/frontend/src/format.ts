const QTY_FORMAT = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 3 });
const DATE_FORMAT = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});
const MONTH_FORMAT = new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric" });

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;
const YYYYMM = /^(\d{4})(\d{2})$/;
const MS_PER_DAY = 86_400_000;

/** UTC midnight of an ISO "YYYY-MM-DD" date, or null when the input is not one. */
function parseIsoDate(iso: string): number | null {
  const m = ISO_DATE.exec(iso);
  return m ? Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;
}

/** en-GB grouping, up to 3 decimals, trailing zeros dropped: 2035876.5 -> "2,035,876.5". */
export function formatQty(n: number): string {
  return QTY_FORMAT.format(n + 0); // + 0 turns -0 into 0, so it never renders as "-0"
}

/** "2026-08-30" -> "30 Aug 2026", independent of the browser time zone. */
export function formatDate(iso: string): string {
  const utc = parseIsoDate(iso);
  return utc === null ? iso : DATE_FORMAT.format(new Date(utc));
}

/** "202608" -> "Aug 2026"; any other input is returned unchanged. */
export function formatMonth(yyyymm: string): string {
  const m = YYYYMM.exec(yyyymm);
  const month = m ? Number(m[2]) : 0;
  if (!m || month < 1 || month > 12) return yyyymm;
  return MONTH_FORMAT.format(new Date(Number(m[1]), month - 1, 1));
}

/** Whole days between an ISO date and `today`, both taken at UTC midnight. */
export function daysOld(iso: string, today: Date): number {
  const then = parseIsoDate(iso);
  if (then === null) return 0;
  const now = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  return Math.floor((now - then) / MS_PER_DAY);
}

/** Share of the shortage the movable quantity covers, 0..100, rounded; 0 when no shortage. */
export function coveragePct(movable: number, shortage: number): number {
  return shortage <= 0 ? 0 : Math.round(Math.min(movable / shortage, 1) * 100);
}
