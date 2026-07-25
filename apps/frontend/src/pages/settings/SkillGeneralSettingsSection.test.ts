// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../../lib/api";
import type { SkillRecord } from "../../types";
import SkillGeneralSettingsSection from "./SkillGeneralSettingsSection.vue";

const skill: SkillRecord = {
  id: "skill-1",
  slug: "example-skill",
  display_name: "示例技能",
  owner_ref: "owner",
  current_version_id: "version-1",
  lifecycle_status: "active",
  tags: [],
};

describe("SkillGeneralSettingsSection", () => {
  afterEach(() => vi.restoreAllMocks());

  it("renames with the current slug as concurrency protection", async () => {
    const update = vi.spyOn(api, "updateSkill").mockResolvedValue({ ...skill, slug: "renamed-skill" });
    const wrapper = mount(SkillGeneralSettingsSection, { props: { skill, canEdit: true } });

    await wrapper.get('input[aria-label="Skill ID"]').setValue("renamed-skill");
    expect(wrapper.text()).toContain("自动生成新的 Patch 版本");
    await wrapper.get("button.primary-button").trigger("click");
    await flushPromises();

    expect(update).toHaveBeenCalledWith("skill-1", {
      slug: "renamed-skill",
      expected_slug: "example-skill",
      owner_ref: "owner",
      display_name: "示例技能",
    });
    expect(wrapper.emitted("refresh")).toHaveLength(1);
  });

  it("updates and clears the optional Chinese name without changing the slug", async () => {
    const update = vi.spyOn(api, "updateSkill").mockResolvedValue({ ...skill, display_name: null });
    const wrapper = mount(SkillGeneralSettingsSection, { props: { skill, canEdit: true } });

    await wrapper.get('input[placeholder="例如 BGP 会话故障排查"]').setValue("   ");
    await wrapper.get("button.primary-button").trigger("click");
    await flushPromises();

    expect(update).toHaveBeenCalledWith("skill-1", {
      slug: "example-skill",
      expected_slug: "example-skill",
      owner_ref: "owner",
      display_name: null,
    });
  });

  it("blocks invalid slugs and keeps server conflicts visible", async () => {
    const update = vi.spyOn(api, "updateSkill").mockRejectedValue(new ApiError("Skill ID 已被其他操作修改，请刷新后重试。", 409));
    const wrapper = mount(SkillGeneralSettingsSection, { props: { skill, canEdit: true } });
    const slug = wrapper.get('input[aria-label="Skill ID"]');

    await slug.setValue("Invalid ID");
    expect(wrapper.get("button.primary-button").attributes("disabled")).toBeDefined();
    await slug.setValue("renamed-skill");
    await wrapper.get("button.primary-button").trigger("click");
    await flushPromises();

    expect(update).toHaveBeenCalledTimes(1);
    expect(wrapper.emitted("toast")?.[0]?.[0]).toMatchObject({ tone: "danger", message: expect.stringContaining("刷新后重试") });
    expect((slug.element as HTMLInputElement).value).toBe("renamed-skill");
  });
});
