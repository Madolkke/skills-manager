// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent, h } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../lib/api";
import type { SkillDetail, TagGroup, ToastState } from "../../types";
import WorkflowSkillTagsSection from "./components/WorkflowSkillTagsSection.vue";
import { useWorkflowSkillTags } from "./useWorkflowSkillTags";

afterEach(() => vi.restoreAllMocks());

describe("Workflow Skill Tags", () => {
  it("将 Tag Picker 的完成操作作为显式保存命令", async () => {
    const wrapper = mount(WorkflowSkillTagsSection, {
      props: { tags: [], groups: [tagGroup()], disabled: false, error: "" },
    });

    await wrapper.get("button.secondary-button").trigger("click");
    await wrapper.get('.skill-tag-option input[type="checkbox"]').setValue(true);
    await wrapper.get("button.primary-button").trigger("click");

    const expected = [{ group_id: "domain", value: "network" }];
    expect(wrapper.emitted("change")?.at(-1)).toEqual([expected]);
    expect(wrapper.emitted("save")?.at(-1)).toEqual([expected]);
  });

  it("独立更新 Skill Tags，并在保存失败后允许重试", async () => {
    const skill = skillDetail();
    const refresh = vi.fn();
    const toasts: ToastState[] = [];
    vi.spyOn(api, "listTagGroups").mockResolvedValue([tagGroup()]);
    const update = vi.spyOn(api, "updateSkill")
      .mockRejectedValueOnce(new Error("保存暂时失败"))
      .mockResolvedValue({ ...skill.skill, tags: [{ group_id: "domain", value: "network" }] });

    let state!: ReturnType<typeof useWorkflowSkillTags>;
    const Host = defineComponent({
      setup() {
        state = useWorkflowSkillTags({ skill: () => skill, refresh, toast: (toast) => toasts.push(toast) });
        return () => h("div");
      },
    });
    const wrapper = mount(Host);
    await flushPromises();
    const nextTags = [{ group_id: "domain", value: "network" }];

    await state.save(nextTags);
    expect(state.error.value).toBe("保存暂时失败");
    await state.save(nextTags);

    expect(update).toHaveBeenLastCalledWith("skill-1", { slug: "interface-check", owner_ref: "owner", tags: nextTags });
    expect(state.tags.value).toEqual(nextTags);
    expect(refresh).toHaveBeenCalledOnce();
    expect(toasts.at(-1)).toEqual({ tone: "success", message: "Skill Tags 已保存。" });
    wrapper.unmount();
  });
});

function tagGroup(): TagGroup {
  return {
    id: "domain",
    display_name: "领域",
    description: "",
    sort_order: 0,
    required: false,
    free_form: false,
    values: [{ tag_group_id: "domain", value: "network", display_name: "网络", description: "", sort_order: 0 }],
  };
}

function skillDetail(): SkillDetail {
  return {
    skill: { id: "skill-1", slug: "interface-check", owner_ref: "owner", current_version_id: null, lifecycle_status: "draft", tags: [] },
    summary: {} as SkillDetail["summary"],
    versions: [], eval_sets: [], latest_eval_runs: [], role_assignments: [], audit_events: [], capabilities: null, workflow: null,
  };
}
