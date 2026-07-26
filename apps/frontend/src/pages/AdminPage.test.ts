// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../lib/api";
import AdminPage from "./AdminPage.vue";

describe("AdminPage authentication", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("keeps the console locked and clears an invalid key", async () => {
    const spies = mockAdminLoad();
    spies.skills.mockRejectedValue(new ApiError("Invalid admin console key.", 403));
    const wrapper = mountPage();

    await wrapper.get('input[type="password"]').setValue("wrong-key");
    await wrapper.get(".admin-login .primary-button").trigger("click");
    await flushPromises();

    expect(wrapper.find(".admin-login").exists()).toBe(true);
    expect(wrapper.find(".admin-nav-row").exists()).toBe(false);
    expect(sessionStorage.getItem("skillhub.admin.key")).toBeNull();
    expect(wrapper.emitted("toast")?.at(-1)?.[0]).toEqual({ tone: "danger", message: "后台密钥无效，请重新输入。" });
  });

  it("enters the console only after the admin data request succeeds", async () => {
    mockAdminLoad();
    const wrapper = mountPage();

    await wrapper.get('input[type="password"]').setValue("correct-key");
    await wrapper.get(".admin-login .primary-button").trigger("click");
    await flushPromises();

    expect(wrapper.find(".admin-login").exists()).toBe(false);
    expect(wrapper.find(".admin-nav-row").exists()).toBe(true);
    expect(sessionStorage.getItem("skillhub.admin.key")).toBe("correct-key");
  });

  it("revalidates a cached key and rejects it when the page mounts", async () => {
    sessionStorage.setItem("skillhub.admin.key", "expired-key");
    const spies = mockAdminLoad();
    spies.skills.mockRejectedValue(new ApiError("Invalid admin console key.", 403));
    const wrapper = mountPage();
    await flushPromises();

    expect(spies.skills).toHaveBeenCalledOnce();
    expect(wrapper.find(".admin-login").exists()).toBe(true);
    expect(wrapper.find(".admin-nav-row").exists()).toBe(false);
    expect(sessionStorage.getItem("skillhub.admin.key")).toBeNull();
  });

  it("locks an open console when a refresh returns 403", async () => {
    const spies = mockAdminLoad();
    spies.skills.mockResolvedValueOnce([]).mockRejectedValueOnce(new ApiError("Invalid admin console key.", 403));
    const wrapper = mountPage();
    await wrapper.get('input[type="password"]').setValue("temporary-key");
    await wrapper.get(".admin-login .primary-button").trigger("click");
    await flushPromises();

    await wrapper.get(".admin-nav-row .secondary-button").trigger("click");
    await flushPromises();

    expect(wrapper.find(".admin-login").exists()).toBe(true);
    expect(sessionStorage.getItem("skillhub.admin.key")).toBeNull();
  });
});

function mountPage() {
  return mount(AdminPage, {
    global: {
      stubs: {
        AdminOverviewTab: true,
      },
    },
  });
}

function mockAdminLoad() {
  return {
    skills: vi.spyOn(api, "adminListSkills").mockResolvedValue([]),
    groups: vi.spyOn(api, "adminListGroups").mockResolvedValue([]),
    tagGroups: vi.spyOn(api, "adminListTagGroups").mockResolvedValue([]),
    cascades: vi.spyOn(api, "adminListTagCascades").mockResolvedValue({ relations: [], diagnostics: [] }),
    roles: vi.spyOn(api, "adminListRoleAssignments").mockResolvedValue([]),
    targets: vi.spyOn(api, "adminListPublishTargets").mockResolvedValue([]),
    checks: vi.spyOn(api, "adminListPublishGateChecks").mockResolvedValue([]),
    records: vi.spyOn(api, "adminListPublishRecords").mockResolvedValue([]),
    workers: vi.spyOn(api, "adminListWorkers").mockResolvedValue({} as never),
    agents: vi.spyOn(api, "adminListOpencodeAgents").mockResolvedValue([]),
    providers: vi.spyOn(api, "listOpencodeProviders").mockResolvedValue({} as never),
  };
}
