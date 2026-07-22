// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../../lib/api";
import SkillDangerSettingsSection from "./SkillDangerSettingsSection.vue";

const defaultProps = {
  skillId: "skill-1",
  slug: "example-skill",
  canDelete: true,
};

describe("SkillDangerSettingsSection", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows the danger zone but disables deletion without permission", () => {
    const wrapper = mountSection({ canDelete: false });

    expect(wrapper.get('[data-testid="open-delete-skill"]').attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("只有 owner 或 admin 可以永久删除当前 Skill");
  });

  it("requires an exact slug and sends it in the DELETE body", async () => {
    const deleteSpy = vi.spyOn(api, "deleteSkill").mockResolvedValue({ ok: true });
    const wrapper = mountSection();
    await wrapper.get('[data-testid="open-delete-skill"]').trigger("click");
    const submit = wrapper.get('[data-testid="confirm-delete-skill"]');
    const input = wrapper.get('[data-testid="delete-skill-confirmation"]');

    await input.setValue("Example-skill");
    expect(submit.attributes("disabled")).toBeDefined();
    await input.setValue("example-skill");
    expect(submit.attributes("disabled")).toBeUndefined();
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(deleteSpy).toHaveBeenCalledWith("skill-1", "example-skill");
    expect(wrapper.emitted("deleted")).toHaveLength(1);
  });

  it("keeps the modal and confirmation when the server returns 409", async () => {
    vi.spyOn(api, "deleteSkill").mockRejectedValue(
      new ApiError("Skill 存在排队中或运行中的任务，任务结束后才能永久删除。", 409),
    );
    const wrapper = mountSection();
    await wrapper.get('[data-testid="open-delete-skill"]').trigger("click");
    const input = wrapper.get('[data-testid="delete-skill-confirmation"]');
    await input.setValue("example-skill");
    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(wrapper.find("[role=dialog]").exists()).toBe(true);
    expect((input.element as HTMLInputElement).value).toBe("example-skill");
    expect(wrapper.get("[role=alert]").text()).toContain("任务结束后才能永久删除");
    expect(wrapper.emitted("deleted")).toBeUndefined();
  });

  it("prevents duplicate submissions while deletion is pending", async () => {
    let resolveRequest: ((value: { ok: boolean }) => void) | undefined;
    const pending = new Promise<{ ok: boolean }>((resolve) => {
      resolveRequest = resolve;
    });
    const deleteSpy = vi.spyOn(api, "deleteSkill").mockReturnValue(pending);
    const wrapper = mountSection();
    await wrapper.get('[data-testid="open-delete-skill"]').trigger("click");
    await wrapper.get('[data-testid="delete-skill-confirmation"]').setValue("example-skill");
    await wrapper.get("form").trigger("submit");
    await wrapper.get("form").trigger("submit");

    expect(deleteSpy).toHaveBeenCalledTimes(1);
    resolveRequest?.({ ok: true });
    await flushPromises();
  });
});

function mountSection(overrides: Partial<typeof defaultProps> = {}) {
  return mount(SkillDangerSettingsSection, {
    props: { ...defaultProps, ...overrides },
    global: { stubs: { Teleport: true } },
  });
}
