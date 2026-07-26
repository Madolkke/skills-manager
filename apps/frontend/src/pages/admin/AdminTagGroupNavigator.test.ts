// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { TagGroup } from "../../types";
import AdminTagGroupNavigator from "./AdminTagGroupNavigator.vue";

const groups = [
  group("scope", "场景", null),
  group("provider", "云厂商", { group_id: "scope", value: "cloud" }),
] as TagGroup[];
groups[0].values = [{ tag_group_id: "scope", value: "cloud", display_name: "云平台", description: "", sort_order: 0 }];

describe("AdminTagGroupNavigator", () => {
  it("shows full paths and emits the selected group", async () => {
    const wrapper = mount(AdminTagGroupNavigator, { props: { groups, selectedGroupId: "scope" } });
    expect(wrapper.text()).toContain("场景 / 云平台 / 云厂商");
    await wrapper.findAll(".admin-tag-group-option")[1].trigger("click");
    expect(wrapper.emitted("select")?.[0]).toEqual(["provider"]);
  });

  it("keeps nested groups searchable by their path", async () => {
    const wrapper = mount(AdminTagGroupNavigator, { props: { groups, selectedGroupId: "scope" } });
    await wrapper.get('input[aria-label="搜索 Tag Group"]').setValue("云平台");
    expect(wrapper.findAll(".admin-tag-group-option")).toHaveLength(1);
    expect(wrapper.text()).toContain("云厂商");
  });
});

function group(id: string, displayName: string, parent: TagGroup["parent"]): TagGroup {
  return { id, display_name: displayName, description: "", sort_order: 0, required: false, free_form: false, parent, values: [] };
}
