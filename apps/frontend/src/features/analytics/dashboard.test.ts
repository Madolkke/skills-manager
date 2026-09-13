// @vitest-environment jsdom
import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AdminAnalyticsTab from "./AdminAnalyticsTab.vue";
import { getAnalytics } from "./api";
import type { AnalyticsOverview } from "./types";

vi.mock("./api", () => ({ getAnalytics: vi.fn() }));

/** 返回未采集历史的空看板，用于验证空值与零的区别。 */
function emptyResult(): AnalyticsOverview {
  return { start_date: "2025-01-01", end_date: "2025-01-31", granularity: "month", timezone: "Asia/Shanghai",
    generated_at: "2026-09-13T01:00:00Z", visits_started_at: "2026-09-13T00:00:00Z", demo_started_at: null,
    includes_demo: false, creation_history_note: "历史覆盖说明", coverage: "none",
    metrics: { total_skills: 0, new_skills: 0, pv: null, uv: null }, trend: [], popular: [] };
}

describe("运营看板界面", () => {
  beforeEach(() => vi.mocked(getAnalytics).mockReset());

  it("loads on mount, distinguishes uncollected data and updates date presets", async () => {
    vi.mocked(getAnalytics).mockResolvedValue(emptyResult());
    const wrapper = mount(AdminAnalyticsTab, { global: { stubs: { AnalyticsChart: true } } });
    await flushPromises();
    expect(wrapper.text()).toContain("未采集");
    expect(wrapper.text()).toContain("访问采集尚未覆盖此期间");
    expect(wrapper.text()).not.toContain("包含模拟数据");
    await wrapper.findAll("button").find((button) => button.text() === "上月")!.trigger("click");
    await flushPromises();
    expect(vi.mocked(getAnalytics).mock.calls.at(-1)![0].granularity).toBe("day");
    wrapper.unmount();
  });

  it("renders demo and deleted markers, exposes data table and retries errors", async () => {
    vi.mocked(getAnalytics).mockRejectedValueOnce(new Error("暂时失败")).mockResolvedValue({
      ...emptyResult(), includes_demo: true, coverage: "complete", popular: [
        { skill_id: "deleted", name: "历史 Skill", owner_ref: "owner", pv: 3, uv: 1, deleted: true },
      ], trend: [{ date: "2025-01-01", new_skills: 1, pv: 3, uv: 1, coverage: "complete" }],
    });
    const wrapper = mount(AdminAnalyticsTab, { global: { stubs: { AnalyticsChart: true } } });
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toContain("暂时失败");
    await wrapper.get('[role="alert"] button').trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("包含模拟数据");
    expect(wrapper.text()).toContain("历史 Skill · 已删除");
    expect(wrapper.findAll("a")).toHaveLength(0);
    expect(wrapper.get("details table").text()).toContain("2025-01-01");
    wrapper.unmount();
  });
});
