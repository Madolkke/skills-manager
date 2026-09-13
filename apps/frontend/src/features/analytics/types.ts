export type AnalyticsRange = { start_date: string; end_date: string; granularity: "day" | "month" };
export type Coverage = "none" | "partial" | "complete";
export type AnalyticsBucket = { date: string; new_skills: number; pv: number | null; uv: number | null; coverage: Coverage };
export type PopularSkill = { skill_id: string; name: string; owner_ref: string; pv: number; uv: number; deleted: boolean };
export type AnalyticsOverview = AnalyticsRange & {
  timezone: "Asia/Shanghai";
  generated_at: string;
  visits_started_at: string;
  demo_started_at: string | null;
  includes_demo: boolean;
  creation_history_note: string;
  coverage: Coverage;
  metrics: { total_skills: number; new_skills: number; pv: number | null; uv: number | null };
  trend: AnalyticsBucket[];
  popular: PopularSkill[];
};
