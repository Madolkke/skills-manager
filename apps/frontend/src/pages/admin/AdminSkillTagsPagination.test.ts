// @vitest-environment jsdom
import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, ref } from "vue";
import { paginationApi } from "../../lib/api/paginationApi";
import type { SkillSummary, SkillTagPayload, TagGroup } from "../../types";
import AdminSkillTagsTab from "./AdminSkillTagsTab.vue";

afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); history.replaceState({}, "", "/"); });

describe("Skill Tags 跨页草稿", () => {
  it("真实复选框修改在完成前跨页保留，取消和丢弃恢复基线", async () => {
    vi.useFakeTimers();
    vi.spyOn(paginationApi, "skills").mockImplementation(async params => {
      const skill: SkillSummary["skill"] = { id: params.page === 2 ? "second" : "first", slug: "draft-test", display_name: null, owner_ref: "tester", current_version_id: null, lifecycle_status: "active", tags: [] };
      return { items: [{ skill, summary: { skill, current_version: null, primary_eval_set: null, latest_accepted_eval_run: null }, workflow: null }],
        total: 21, page: Number(params.page), page_size: 20, counts: {}, tag_counts: {} };
    });
    const groups = [{ id: "domain", display_name: "领域", required: false, free_form: false, display_mode: "checkbox", values: [{ value: "network", display_name: "网络" }] }] as TagGroup[];
    const drafts = ref<Record<string, SkillTagPayload[]>>({});
    const wrapper = mount(defineComponent({ setup: () => () => h(AdminSkillTagsTab, {
      tagDrafts: drafts.value, tagGroups: groups,
      onUpdateDraft: (id: string, tags: SkillTagPayload[]) => { drafts.value[id] = tags; },
      onDiscard: (id?: string) => { if (id) delete drafts.value[id]; else drafts.value = {}; },
    }) }));
    const click = async (text: string) => { await wrapper.findAll("button").find(b => b.text() === text)!.trigger("click"); await vi.advanceTimersByTimeAsync(1); await flushPromises(); };
    await flushPromises(); await click("编辑 Tags");
    await wrapper.get('input[type="checkbox"]').setValue(true);
    expect(drafts.value.first).toEqual([{ group_id: "domain", value: "network" }]);
    await click("下一页"); await click("上一页"); await click("编辑 Tags");
    expect((wrapper.get('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(true);
    await click("取消"); expect(drafts.value).toEqual({});
    await click("编辑 Tags"); await wrapper.get('input[type="checkbox"]').setValue(true);
    await click("丢弃全部草稿"); expect(drafts.value).toEqual({});
    expect(wrapper.find('input[type="checkbox"]').exists()).toBe(false);
    expect(wrapper.text()).toContain("尚未添加 Tag"); wrapper.unmount();
  });
  it("翻页及标签页重新进入保留作者草稿，刷新不覆盖草稿", async () => {
    vi.useFakeTimers();
    const skill = (id: string) => ({ skill: { id, slug: id, tags: [{ group_id: "domain", value: "saved" }] }, summary: {}, workflow: null }) as SkillSummary;
    vi.spyOn(paginationApi, "skills").mockImplementation(async params => ({
      items: [skill(params.page === 2 ? "second" : "first")], total: 21,
      page: Number(params.page), page_size: 20, counts: {}, tag_counts: {},
    }));
    const drafts = { first: [{ group_id: "domain", value: "draft" }] };
    const options = { props: { tagDrafts: drafts, tagGroups: [] }, global: { stubs: { SkillTagPicker: true } } };
    let wrapper = mount(AdminSkillTagsTab, options); await flushPromises();
    expect(wrapper.getComponent({ name: "SkillTagPicker" }).props("value")).toEqual(drafts.first);
    await wrapper.findAll("button").find(button => button.text() === "下一页")!.trigger("click");
    await vi.advanceTimersByTimeAsync(1); await flushPromises(); expect(wrapper.text()).toContain("second");
    await wrapper.findAll("button").find(button => button.text() === "上一页")!.trigger("click");
    await vi.advanceTimersByTimeAsync(1); await flushPromises();
    expect(wrapper.getComponent({ name: "SkillTagPicker" }).props("value")).toEqual(drafts.first);
    wrapper.unmount(); wrapper = mount(AdminSkillTagsTab, options); await flushPromises();
    await wrapper.setProps({ refreshToken: 1 }); await flushPromises();
    expect(wrapper.getComponent({ name: "SkillTagPicker" }).props("value")).toEqual(drafts.first);
    expect(wrapper.text()).toContain("1 个未保存草稿"); wrapper.unmount();
  });
});
