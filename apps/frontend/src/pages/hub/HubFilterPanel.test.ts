// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { SkillTagPayload, TagGroup } from "../../types";
import HubFilterPanel from "./HubFilterPanel.vue";

const groups: TagGroup[] = [
  group("scope", "场景", [["cloud", "云平台"]]),
  group("provider", "云厂商", [["aws", "AWS"]], { parent: { group_id: "scope", value: "cloud" } }),
  group("runtime", "运行环境", [["eks", "EKS"]], { parent: { group_id: "provider", value: "aws" } }),
  group("team", "团队", [["platform", "平台团队"]]),
];

describe("HubFilterPanel", () => {
  it("shows only the selected cascade leaf while retaining the full path for context", async () => {
    const selectedTags: SkillTagPayload[] = [
      { group_id: "scope", value: "cloud" },
      { group_id: "provider", value: "aws" },
      { group_id: "runtime", value: "eks" },
    ];
    const wrapper = mountPanel(selectedTags);
    const chips = wrapper.findAll(".hub-selected-tags .tag-chip.editable");

    expect(chips).toHaveLength(1);
    expect(chips[0]!.get(".tag-chip-label").text()).toBe("EKS");
    expect(chips[0]!.text()).not.toContain("场景 / 云平台");
    expect(chips[0]!.attributes("title")).toBe("场景 / 云平台 / 云厂商 / AWS / 运行环境 / EKS");

    const removeButton = chips[0]!.get("button");
    expect(removeButton.attributes("aria-label")).toBe("移除 场景 / 云平台 / 云厂商 / AWS / 运行环境 / EKS");
    await removeButton.trigger("click");
    expect(wrapper.emitted("toggle-tag")?.[0]).toEqual([{ group_id: "runtime", value: "eks" }]);
  });

  it("keeps an independently selected root tag as its own leaf chip", () => {
    const wrapper = mountPanel([
      { group_id: "scope", value: "cloud" },
      { group_id: "provider", value: "aws" },
      { group_id: "runtime", value: "eks" },
      { group_id: "team", value: "platform" },
    ]);
    const labels = wrapper.findAll(".hub-selected-tags .tag-chip-label").map((chip) => chip.text());

    expect(labels).toEqual(["EKS", "平台团队"]);
  });
});

function mountPanel(selectedTags: SkillTagPayload[]) {
  return mount(HubFilterPanel, {
    props: {
      query: "",
      tagGroups: groups,
      selectedTags,
      tagCounts: {},
      loadingTags: false,
      tagError: "",
    },
  });
}

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
