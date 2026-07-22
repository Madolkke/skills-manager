// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { TagCascadeOverview, TagGroup } from "../../types";
import AdminTagCascadesTab from "./AdminTagCascadesTab.vue";

function group(id: string, displayName: string, values: Array<[string, string]>, options: Partial<TagGroup> = {}): TagGroup {
  return {
    id,
    display_name: displayName,
    description: "",
    sort_order: 0,
    required: false,
    free_form: false,
    values: values.map(([value, label], index) => ({
      tag_group_id: id,
      value,
      display_name: label,
      description: "",
      sort_order: index,
    })),
    ...options,
  };
}

const tagGroups = [
  group("platform", "平台", [["python", "Python"], ["node", "Node.js"]]),
  group("runtime", "运行时", [["cpython", "CPython"]], { required: true }),
  group("region", "区域", [["cn", "中国"]], { sort_order: 2 }),
];

const overview: TagCascadeOverview = {
  relations: [{ child_group_id: "runtime", parent_group_id: "platform", parent_value: "python" }],
  diagnostics: [{ group_id: "runtime", orphaned_skill_ids: ["skill-1"], missing_required_skill_ids: ["skill-2"] }],
};

describe("AdminTagCascadesTab", () => {
  it("renders summary, hierarchy context and diagnostics", async () => {
    const wrapper = mount(AdminTagCascadesTab, { props: { tagGroups, overview } });
    const metrics = wrapper.findAll(".cascade-metric-grid .admin-metric-card").map((item) => item.text());

    expect(metrics).toEqual(["Group 总数3", "根级 Group2", "级联关系1", "异常项2"]);
    expect(wrapper.get('[data-group-id="runtime"].group').text()).toContain("平台 / Python");
    expect(wrapper.get('[data-group-id="platform"][data-value="python"]').text()).toContain("1 个子 Group");

    await wrapper.get('[data-group-id="runtime"].group .cascade-issue-button').trigger("click");
    expect(wrapper.emitted("inspect")?.[0]).toEqual([{
      groupId: "runtime",
      kind: "orphaned",
      skillIds: ["skill-1"],
    }]);
  });

  it("collapses and restores descendants for a group", async () => {
    const wrapper = mount(AdminTagCascadesTab, { props: { tagGroups, overview } });
    const toggle = wrapper.get('[data-group-id="platform"].group .cascade-expand-button');

    await toggle.trigger("click");
    expect(wrapper.find('[data-group-id="platform"][data-value="python"]').exists()).toBe(false);
    expect(wrapper.find('[data-group-id="runtime"].group').exists()).toBe(false);

    await toggle.trigger("click");
    expect(wrapper.find('[data-group-id="platform"][data-value="python"]').exists()).toBe(true);
    expect(wrapper.find('[data-group-id="runtime"].group').exists()).toBe(true);
  });

  it("highlights a parent value and emits the selected root group", async () => {
    const wrapper = mount(AdminTagCascadesTab, { props: { tagGroups, overview } });
    const valueRow = wrapper.get('[data-group-id="platform"][data-value="python"]');

    await valueRow.get(".cascade-attach-button").trigger("click");
    expect(valueRow.classes()).toContain("selected");
    expect(wrapper.get(".cascade-link-context").text()).toContain("平台 / Python");
    expect((wrapper.get('select[aria-label="选择子 Tag Group"]').element as HTMLSelectElement).value).toBe("region");

    await wrapper.get(".cascade-link-editor .primary-button").trigger("click");
    expect(wrapper.emitted("attach")?.[0]).toEqual([{
      parent_group_id: "platform",
      parent_value: "python",
      child_group_id: "region",
    }]);
  });

  it("explains when no root group can be mounted", async () => {
    const wrapper = mount(AdminTagCascadesTab, { props: { tagGroups: tagGroups.slice(0, 2), overview } });

    await wrapper.get('[data-group-id="platform"][data-value="python"] .cascade-attach-button').trigger("click");
    expect(wrapper.text()).toContain("没有可挂载的根级 Group");
    expect(wrapper.get(".cascade-link-editor .primary-button").attributes("disabled")).toBeDefined();
  });
});
