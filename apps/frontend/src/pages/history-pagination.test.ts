// @vitest-environment jsdom
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { paginationApi, type SkillCore } from "../lib/api/paginationApi";
import type { EvalRunDetail } from "../types";
import HistoryPage from "./HistoryPage.vue";

afterEach(() => { vi.restoreAllMocks(); history.replaceState({}, "", "/"); });

describe("测评历史按需读取", () => {
  it("切换测评集回到第一页，空结果不会继续显示旧运行", async () => {
    history.replaceState({}, "", "/skills?runs_page=3");
    const one = { id: "one", name: "Primary" }, two = { id: "two", name: "Empty" };
    const skill = { skill: { id: "skill" }, eval_sets: [one, two], summary: { primary_eval_set: one } } as SkillCore;
    const row = { eval_run: { id: "old", eval_set_id: "one", created_at: "2026-09-18", summary: {} }, skill_version: { version: "1.0.0" }, eval_set: one };
    const fetcher = vi.spyOn(paginationApi, "runs").mockImplementation(async (_id, params) =>
      ({ items: params.eval_set_id === "one" ? [row] : [], total: params.eval_set_id === "one" ? 61 : 0, page: Number(params.page), page_size: 20 }) as Awaited<ReturnType<typeof paginationApi.runs>>);
    vi.spyOn(api, "getEvalRun").mockResolvedValue({ ...row, case_results: [] } as unknown as EvalRunDetail);
    const wrapper = mount(HistoryPage, { props: { skill, selectedRunId: null, selectedEvalSetId: "one" } });
    await flushPromises(); expect(wrapper.find(".run-evidence-head").exists()).toBe(true);
    await wrapper.setProps({ selectedEvalSetId: "two" });
    expect(wrapper.find(".run-evidence-head").exists()).toBe(false);
    await new Promise(resolve => setTimeout(resolve, 350)); await flushPromises();
    expect(fetcher).toHaveBeenLastCalledWith("skill", expect.objectContaining({ page: 1, eval_set_id: "two" }), expect.any(AbortSignal));
    expect(wrapper.text()).toContain("还没有测评记录");
    expect(wrapper.find(".run-evidence-head").exists()).toBe(false);
    wrapper.unmount();
  });

  it("第三页保留直达运行，编号基于总数，快速选择丢弃旧详情", async () => {
    history.replaceState({}, "", "/skills?runs_page=3");
    const evalSet = { id: "set", name: "Primary", description: "" };
    const skill = { skill: { id: "skill" }, eval_sets: [evalSet], summary: { primary_eval_set: evalSet } } as SkillCore;
    vi.spyOn(paginationApi, "runs").mockResolvedValue({ items: [{ eval_run: { id: "row", eval_set_id: "set", created_at: "2026-09-18", summary: {} }, skill_version: { version: "1.0.0" }, eval_set: evalSet }], total: 61, page: 3, page_size: 20 } as Awaited<ReturnType<typeof paginationApi.runs>>);
    const pending = new Map<string, (value: EvalRunDetail) => void>();
    vi.spyOn(api, "getEvalRun").mockImplementation(id => new Promise(resolve => pending.set(id, resolve)));
    const wrapper = mount(HistoryPage, { props: { skill, selectedRunId: "old", selectedEvalSetId: "set" } });
    await flushPromises();
    expect(wrapper.text()).toContain("第 21 次");
    expect(wrapper.text()).not.toContain("最新");
    expect(api.getEvalRun).toHaveBeenCalledWith("old");
    expect(api.getEvalRun).not.toHaveBeenCalledWith("row");
    await wrapper.setProps({ selectedRunId: "new" });
    const detail = (version: string) => ({ eval_run: { id: version, summary: {}, run_context_hash: "hash", created_at: "2026-09-18" }, skill_version: { version }, eval_set: evalSet, case_results: [] }) as unknown as EvalRunDetail;
    pending.get("new")!(detail("2.0.0")); await flushPromises();
    pending.get("old")!(detail("1.0.0")); await flushPromises();
    expect(wrapper.get(".run-evidence-head h2").text()).toContain("2.0.0");
    wrapper.unmount();
  });
});
