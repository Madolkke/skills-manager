// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils";
import { computed, defineComponent, ref } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import { resetCommandLibrarySession } from "./commandLibrarySession";
import { useCommandLibrarySearch } from "./useCommandLibrarySearch";

const SearchHarness = defineComponent({
  props: { enabled: { type: Boolean, default: true } },
  setup(props) {
    const query = ref("");
    return { ...useCommandLibrarySearch(query, computed(() => props.enabled)) };
  },
  template: "<div />",
});

describe("useCommandLibrarySearch", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    resetCommandLibrarySession();
    vi.useRealTimers();
  });

  it("空查询时默认加载系统命令，开启 Toggle 后请求用户命令", async () => {
    vi.useFakeTimers();
    const searchCommandLibrary = vi.spyOn(api, "searchCommandLibrary");
    searchCommandLibrary.mockResolvedValue({ results: [] });
    const wrapper = mount(SearchHarness);

    await vi.advanceTimersByTimeAsync(180);
    await flushPromises();
    expect(searchCommandLibrary).toHaveBeenLastCalledWith("", false, undefined, expect.any(AbortSignal));

    wrapper.vm.includeUser = true;
    await vi.advanceTimersByTimeAsync(180);
    await flushPromises();
    expect(searchCommandLibrary).toHaveBeenLastCalledWith("", true, undefined, expect.any(AbortSignal));
    wrapper.unmount();
  });

  it("离开命令行类型时立即清空远端结果并中止请求", async () => {
    vi.useFakeTimers();
    const searchCommandLibrary = vi.spyOn(api, "searchCommandLibrary");
    searchCommandLibrary.mockResolvedValue({ results: [{
      id: "system-1",
      source: "system",
      key: "system-1",
      expression: "display system",
      metadata: { name: "系统" },
    }] });
    const wrapper = mount(SearchHarness);

    await vi.advanceTimersByTimeAsync(180);
    await flushPromises();
    expect(wrapper.vm.results).toHaveLength(1);
    await wrapper.setProps({ enabled: false });
    await flushPromises();
    expect(wrapper.vm.results).toEqual([]);
    wrapper.unmount();
  });
});
