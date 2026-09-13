import type { AnalyticsRange } from "./types";

/** 返回北京时间的当天日期，避免浏览器所在时区影响筛选。 */
export function shanghaiToday(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

/** 按月份移动到目标月首日。 */
export function monthStart(value: string, offset = 0): string {
  const [year, month] = value.split("-").map(Number);
  return new Date(Date.UTC(year!, month! - 1 + offset, 1)).toISOString().slice(0, 10);
}

/** 生成常用运营日期范围。 */
export function presetRange(preset: "current" | "previous" | "year", today = shanghaiToday()): AnalyticsRange {
  if (preset === "previous") {
    const last = new Date(`${monthStart(today)}T00:00:00Z`);
    last.setUTCDate(0);
    return { start_date: monthStart(today, -1), end_date: last.toISOString().slice(0, 10), granularity: "day" };
  }
  return { start_date: monthStart(today, preset === "year" ? -11 : 0), end_date: today, granularity: preset === "year" ? "month" : "day" };
}

/** 将点击月份转换为日趋势范围，本月截止今天。 */
export function drillMonth(month: string, today = shanghaiToday()): AnalyticsRange {
  const last = new Date(`${monthStart(month, 1)}T00:00:00Z`);
  last.setUTCDate(0);
  return { start_date: monthStart(month), end_date: [last.toISOString().slice(0, 10), today].sort()[0]!, granularity: "day" };
}
