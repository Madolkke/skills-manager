// @vitest-environment jsdom
import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, h, ref } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePagedQuery } from "./usePagedQuery";
import { useListFilters } from "./useListFilters";

/** 所有状态测试共用同一个最小宿主，销毁时运行 composable 清理。 */
function mountQuery(setup: () => void) { return mount(defineComponent({ setup() { setup(); return () => h("div"); } })); }

describe("服务端分页状态", () => {
  beforeEach(() => { vi.useFakeTimers(); history.replaceState({}, "", "/skills"); });
  afterEach(() => vi.useRealTimers());
  it("过期请求不能覆盖最新页，筛选重置页码且保留完整总数", async () => {
    const pending: Array<(result: { items: string[]; total: number; page: number; page_size: number }) => void> = [];
    const fetcher = vi.fn(() => new Promise<{ items: string[]; total: number; page: number; page_size: number }>(resolve => pending.push(resolve)));
    const query = ref("");
    let state!: ReturnType<typeof usePagedQuery<Awaited<ReturnType<typeof fetcher>>>>;
    const host = mountQuery(() => { state = usePagedQuery("test", () => ({ query: query.value }), fetcher); });
    state.page.value = 2;
    await vi.advanceTimersByTimeAsync(1);
    pending[1]({ items: ["第二页"], total: 43, page: 2, page_size: 20 }); await flushPromises();
    pending[0]({ items: ["过期第一页"], total: 43, page: 1, page_size: 20 }); await flushPromises();
    expect(state.items.value).toEqual(["第二页"]);
    expect(state.total.value).toBe(43);
    query.value = "匹配"; await vi.advanceTimersByTimeAsync(100);
    expect(fetcher).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(201);
    expect(state.page.value).toBe(1);
    expect(fetcher).toHaveBeenLastCalledWith(expect.objectContaining({ query: "匹配", page: 1 }), expect.any(AbortSignal));
    host.unmount();
  });
  it("请求失败可重试，页码越界自动回到有效页", async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new Error("断开连接"))
      .mockResolvedValue({ items: ["记录"], total: 1, page: 1, page_size: 20 });
    let state!: ReturnType<typeof usePagedQuery>;
    const host = mountQuery(() => { state = usePagedQuery("test", () => ({}), fetcher); });
    await flushPromises(); expect(state.error.value).toBe("断开连接");
    await state.reload(); expect(state.error.value).toBe("");
    state.page.value = 4; await vi.advanceTimersByTimeAsync(10);
    expect(state.page.value).toBe(1);
    expect(state.items.value).toEqual(["记录"]);
    host.unmount();
  });
  it("历史返回恢复页码，不新增浏览器历史", async () => {
    const fetcher = vi.fn().mockResolvedValue({ items: [], total: 200, page: 3, page_size: 20 });
    let state!: ReturnType<typeof usePagedQuery>;
    const host = mountQuery(() => { state = usePagedQuery("test", () => ({}), fetcher); });
    history.replaceState({}, "", "/skills?test_page=3&test_size=50");
    const push = vi.spyOn(history, "pushState");
    window.dispatchEvent(new PopStateEvent("popstate")); await vi.advanceTimersByTimeAsync(1);
    expect(state.page.value).toBe(3); expect(state.pageSize.value).toBe(50); expect(push).not.toHaveBeenCalled();
    host.unmount(); push.mockRestore();
  });
  it("筛选和页码一起从历史恢复，不被筛选 watcher 重置", async () => {
    const fetcher = vi.fn().mockResolvedValue({ items: [], total: 200, page: 3, page_size: 20 });
    let state!: ReturnType<typeof usePagedQuery>;
    let filters!: { query: string };
    const host = mountQuery(() => { filters = useListFilters("test", { query: "" }); state = usePagedQuery("test", () => filters, fetcher); });
    history.replaceState({}, "", '/skills?test_page=3&test_filters=%7B%22query%22%3A%22old%22%7D');
    const push = vi.spyOn(history, "pushState");
    window.dispatchEvent(new PopStateEvent("popstate")); await vi.advanceTimersByTimeAsync(301);
    expect(filters.query).toBe("old"); expect(state.page.value).toBe(3); expect(push).not.toHaveBeenCalled();
    expect(fetcher).toHaveBeenLastCalledWith(expect.objectContaining({ query: "old", page: 3 }), expect.any(AbortSignal));
    host.unmount(); push.mockRestore();
  });
});
