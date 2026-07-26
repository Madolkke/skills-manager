// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { SkillTagPayload, TagGroup } from "../types";
import SkillTagPicker from "./SkillTagPicker.vue";

const groups: TagGroup[] = [
  group("scope", "场景", [["cloud", "云平台"], ["network", "网络"]], { required: true }),
  group("provider", "云厂商", [["aws", "AWS"]], { required: true, parent: { group_id: "scope", value: "cloud" } }),
  group("runtime", "运行环境", [["eks", "EKS"]], { parent: { group_id: "provider", value: "aws" } }),
];

describe("SkillTagPicker", () => {
  it("expands selected branches and emits every inline change", async () => {
    const wrapper = mount(SkillTagPicker, { props: { value: [], groups, mode: "inline" } });
    expect(wrapper.find('[aria-label="场景 / 云平台 / 云厂商"]').exists()).toBe(false);

    await wrapper.get('[aria-label="场景"] .skill-tag-option input').setValue(true);
    const scope = wrapper.emitted("change")?.at(-1)?.[0] as SkillTagPayload[];
    await wrapper.setProps({ value: scope });

    expect(wrapper.find('[aria-label="场景 / 云平台 / 云厂商"]').exists()).toBe(true);
    await wrapper.get('[aria-label="场景 / 云平台 / 云厂商"] .skill-tag-option input').setValue(true);
    const provider = wrapper.emitted("change")?.at(-1)?.[0] as SkillTagPayload[];
    await wrapper.setProps({ value: provider });
    expect(wrapper.find('[aria-label="场景 / 云平台 / 云厂商 / AWS / 运行环境"]').exists()).toBe(true);
  });

  it("prunes descendants and reports the cleanup", async () => {
    const selected = [
      { group_id: "scope", value: "cloud" },
      { group_id: "provider", value: "aws" },
      { group_id: "runtime", value: "eks" },
    ];
    const wrapper = mount(SkillTagPicker, { props: { value: selected, groups, mode: "inline" } });
    await wrapper.get('[aria-label="场景"] .skill-tag-option input').setValue(false);

    expect(wrapper.emitted("change")?.at(-1)).toEqual([[]]);
    expect(wrapper.text()).toContain("已同时移除 2 个下级 Tag");
  });

  it("keeps staged edits local until completion and supports cancellation", async () => {
    const wrapper = mount(SkillTagPicker, { props: { value: [], groups } });
    await wrapper.get("button.secondary-button").trigger("click");
    await wrapper.get('[aria-label="场景"] .skill-tag-option input').setValue(true);
    await wrapper.findAll("button.secondary-button").at(-1)!.trigger("click");

    expect(wrapper.emitted("change")).toBeUndefined();
    expect(wrapper.find(".skill-tag-branch-list").exists()).toBe(false);
  });

  it("keeps invalid cyclic selections visible for removal", () => {
    const cyclicGroups = [
      group("a", "A", [["one", "一"]], { parent: { group_id: "b", value: "two" } }),
      group("b", "B", [["two", "二"]], { parent: { group_id: "a", value: "one" } }),
    ];
    const wrapper = mount(SkillTagPicker, {
      props: {
        value: [{ group_id: "a", value: "one" }, { group_id: "b", value: "two" }],
        groups: cyclicGroups,
      },
    });

    expect(wrapper.findAll(".skill-tag-selected .tag-chip.warning")).toHaveLength(2);
    expect(wrapper.text()).toContain("A");
    expect(wrapper.text()).toContain("B");
  });
});

function group(id: string, displayName: string, values: Array<[string, string]>, options: Partial<TagGroup> = {}): TagGroup {
  return {
    id,
    display_name: displayName,
    description: "",
    sort_order: 0,
    required: false,
    free_form: false,
    parent: null,
    values: values.map(([value, label], index) => ({ tag_group_id: id, value, display_name: label, description: "", sort_order: index })),
    ...options,
  };
}
