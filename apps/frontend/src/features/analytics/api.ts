import { apiGet, apiSend } from "../../lib/api/httpClient";
import type { AnalyticsOverview, AnalyticsRange } from "./types";

/** 请求后台聚合，不下载原始访问事件。 */
export function getAnalytics(range: AnalyticsRange, signal?: AbortSignal): Promise<AnalyticsOverview> {
  return apiGet(`/api/admin/analytics/overview?${new URLSearchParams(range)}`, { admin: true, signal });
}

/** actor 由通用请求头及服务端会话提供，同一事件重试复用 UUID。 */
export function recordSkillVisit(skillId: string, eventId: string): Promise<{ ok: boolean }> {
  return apiSend(`/api/skills/${encodeURIComponent(skillId)}/visits`, "POST", { event_id: eventId });
}
