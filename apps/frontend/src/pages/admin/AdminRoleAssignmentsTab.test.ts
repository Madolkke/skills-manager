// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { SkillSummary } from "../../types";
import AdminRoleAssignmentsTab from "./AdminRoleAssignmentsTab.vue";

const skill = {
  skill: {
    id: "skill-1",
    slug: "example-skill",
    display_name: "示例技能",
    owner_ref: "owner",
    current_version_id: null,
    lifecycle_status: "active",
    tags: [],
  },
  summary: { skill: null, current_version: null, primary_eval_set: null, latest_accepted_eval_run: null },
  workflow: null,
} as unknown as SkillSummary;

describe("AdminRoleAssignmentsTab", () => {
  it("locks global Skill grants to the only valid user admin combination", async () => {
    const wrapper = mount(AdminRoleAssignmentsTab, { props: { roles: [], tagGroups: [], skills: [skill] } });
    const selects = wrapper.findAll(".admin-role-form select");

    expect(wrapper.text()).toContain("example-skill（示例技能）");
    await selects[1].setValue("global");
    await wrapper.get('input[placeholder="主体 ID"]').setValue("alice");

    const updatedSelects = wrapper.findAll(".admin-role-form select");
    expect((updatedSelects[0].element as HTMLSelectElement).value).toBe("user");
    expect(updatedSelects[0].attributes("disabled")).toBeDefined();
    expect((updatedSelects[2].element as HTMLSelectElement).value).toBe("admin");
    expect(updatedSelects[2].attributes("disabled")).toBeDefined();
    expect(wrapper.get('input[aria-label="授权资源"]').element.getAttribute("value")).toBe("全部当前及未来 Skill");

    await wrapper.get("button.primary-button").trigger("click");
    expect(wrapper.emitted("assign")?.[0]).toEqual([{
      subject_type: "user",
      subject_id: "alice",
      resource_type: "global",
      resource_id: "skills",
      role: "admin",
    }]);
  });

  it("labels existing global grants as all Skills", () => {
    const wrapper = mount(AdminRoleAssignmentsTab, {
      props: {
        skills: [skill],
        tagGroups: [],
        roles: [{
          id: "role-1",
          subject_type: "user",
          subject_id: "alice",
          resource_type: "global",
          resource_id: "skills",
          role: "admin",
          created_by: "admin-console",
        }],
      },
    });

    expect(wrapper.get(".admin-role-table-row").text()).toContain("全部 Skill");
  });
});
