// @vitest-environment jsdom
import { effectScope, ref } from "vue";
import { describe, expect, it, vi } from "vitest";
import type { RouteState } from "../../lib/navigation";
import { drillMonth, presetRange, shanghaiToday } from "./dates";
import { useAnalytics } from "./useAnalytics";
import { useSkillVisit } from "./useSkillVisit";
import type { AnalyticsOverview } from "./types";

/** 构造详情路由，使用同一 ref 模拟所有导航行为。 */
function routeState(): RouteState {
  return { section: "skills", skillId: "a", tab: "overview", selectedCaseId: null, selectedEvalSetId: null, selectedVersionId: null, selectedRunId: null };
}

describe("Skill visits", () => {
  it("counts entry only, ignores tab refresh and editor, rejects stale loads", async () => {
    const route = ref(routeState());
    const client = vi.fn().mockResolvedValue({ ok: true });
    const scope = effectScope();
    const visits = scope.run(() => useSkillVisit(route, client))!;
    const first = visits.token();
    expect(client).not.toHaveBeenCalled();
    await visits.displayed("a", first);
    route.value = { ...route.value, tab: "versions" };
    await visits.displayed("a", first);
    expect(client).toHaveBeenCalledTimes(1);
    route.value = { ...route.value, section: "workflows" };
    await visits.displayed("a", visits.token());
    expect(client).toHaveBeenCalledTimes(1);
    route.value = { ...route.value, section: "skills" };
    await visits.displayed("a", first);
    expect(client).toHaveBeenCalledTimes(1);
    await visits.displayed("a", visits.token());
    expect(client).toHaveBeenCalledTimes(2);
    route.value.skillId = "b";
    await visits.displayed("a", visits.token());
    expect(client).toHaveBeenCalledTimes(2);
    await visits.displayed("b", visits.token());
    expect(client).toHaveBeenCalledTimes(3);
    scope.stop();
  });

  it("retries the same UUID once and a full reload starts another event", async () => {
    const route = ref(routeState());
    const client = vi.fn().mockRejectedValueOnce(new Error("network")).mockResolvedValue({ ok: true });
    const scope = effectScope();
    const visits = scope.run(() => useSkillVisit(route, client))!;
    await visits.displayed("a", visits.token());
    expect(client).toHaveBeenCalledTimes(2);
    expect(client.mock.calls[0]).toEqual(client.mock.calls[1]);
    const reloaded = scope.run(() => useSkillVisit(route, client))!;
    expect(reloaded.token()).not.toBe(visits.token());
    scope.stop();
  });
});

describe("运营日期和加载", () => {
  it("uses Shanghai boundaries, leap month and current-month truncation", () => {
    expect(shanghaiToday(new Date("2026-01-31T16:00:00Z"))).toBe("2026-02-01");
    expect(presetRange("year", "2026-09-13").start_date).toBe("2025-10-01");
    expect(presetRange("previous", "2024-03-03").end_date).toBe("2024-02-29");
    expect(drillMonth("2026-09-01", "2026-09-13").end_date).toBe("2026-09-13");
  });

  it("ignores old requests and recovers after a failed query", async () => {
    let resolveOld!: (value: AnalyticsOverview) => void;
    const client = vi.fn().mockImplementationOnce(() => new Promise<AnalyticsOverview>((resolve) => { resolveOld = resolve; }))
      .mockResolvedValueOnce({ start_date: "new" }).mockRejectedValueOnce(new Error("retry"));
    const scope = effectScope();
    const state = scope.run(() => useAnalytics(client))!;
    const old = state.load();
    await state.load();
    resolveOld({ start_date: "old" } as AnalyticsOverview);
    await old;
    expect(state.data.value?.start_date).toBe("new");
    await state.load();
    expect(state.error.value).toBe("retry");
    expect(state.loading.value).toBe(false);
    client.mockResolvedValueOnce({ start_date: "recovered" });
    await state.load();
    expect(state.data.value?.start_date).toBe("recovered");
    expect(state.error.value).toBe("");
    scope.stop();
  });
});
