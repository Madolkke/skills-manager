// @vitest-environment jsdom

import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "../lib/api";
import { paginationApi } from "../lib/api/paginationApi";
const emptyOverview = { counts: {}, recent_tag_groups: [], recent_roles: [] };
import AdminPage from "./AdminPage.vue";
import { defineComponent } from "vue";
import { useAdminPageState } from "./admin/useAdminPageState";

describe("AdminPage authentication", () => {
  beforeEach(() => sessionStorage.clear());
  afterEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("概览不加载其他后台目录，切换用户组只加载该目录", async () => {
    const spies = mockAdminLoad();
    const wrapper = mountPage();
    await wrapper.get('input[type="password"]').setValue("test-key");
    await wrapper.get(".admin-login .primary-button").trigger("click"); await flushPromises();
    expect(spies.overview).toHaveBeenCalledTimes(1);
    for (const [key, spy] of Object.entries(spies)) if (key !== "overview") expect(spy).not.toHaveBeenCalled();
    await wrapper.findAll("button").find(button => button.text() === "用户组")!.trigger("click"); await flushPromises();
    expect(spies.groups).toHaveBeenCalledTimes(1);
    expect(spies.skills).not.toHaveBeenCalled(); expect(spies.roles).not.toHaveBeenCalled();
    expect(spies.records).not.toHaveBeenCalled(); wrapper.unmount();
    history.replaceState({}, "", "/");
  });

  it("鉴权失效时清理目录并忽略尚未完成的后台请求", async () => {
    history.replaceState({}, "", "/");
    const spies = mockAdminLoad();
    const wrapper = mount(defineComponent({ setup: () => ({ state: useAdminPageState(vi.fn()) }), template: "<div />" }));
    const state = wrapper.vm.state;
    state.key.value = "test-key";
    await state.unlock();
    state.groups.value = [{ id: "old-group" }] as never;
    state.tagDrafts.value = { skill: [] };
    let finish!: (value: never[]) => void;
    spies.expressionFunctions.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    await state.selectAdminTab("expression-functions"); await flushPromises();
    spies.workers.mockRejectedValue(new ApiError("expired", 403));
    await state.refreshWorkers();
    finish([{ id: "late-function" }] as never[]); await flushPromises();
    expect(state.unlocked.value).toBe(false);
    expect(state.groups.value).toEqual([]); expect(state.tagDrafts.value).toEqual({});
    expect(state.expressionFunctions.value).toEqual([]);
    expect(sessionStorage.getItem("skillhub.admin.key")).toBeNull();
    wrapper.unmount(); history.replaceState({}, "", "/");
  });

  it("keeps the console locked and clears an invalid key", async () => {
    const spies = mockAdminLoad();
    spies.overview.mockRejectedValue(new ApiError("Invalid admin console key.", 403));
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
    const spies = mockAdminLoad();
    const wrapper = mountPage();

    await wrapper.get('input[type="password"]').setValue("correct-key");
    await wrapper.get(".admin-login .primary-button").trigger("click");
    await flushPromises();

    expect(wrapper.find(".admin-login").exists()).toBe(false);
    expect(wrapper.find(".admin-nav-row").exists()).toBe(true);
    expect(sessionStorage.getItem("skillhub.admin.key")).toBe("correct-key");
    expect(spies.systemCommands).not.toHaveBeenCalled();
    expect(spies.skills).not.toHaveBeenCalled();
    expect(spies.overview).toHaveBeenCalledOnce();
  });

  it("revalidates a cached key and rejects it when the page mounts", async () => {
    sessionStorage.setItem("skillhub.admin.key", "expired-key");
    const spies = mockAdminLoad();
    spies.overview.mockRejectedValue(new ApiError("Invalid admin console key.", 403));
    const wrapper = mountPage();
    await flushPromises();

    expect(spies.overview).toHaveBeenCalledOnce();
    expect(wrapper.find(".admin-login").exists()).toBe(true);
    expect(wrapper.find(".admin-nav-row").exists()).toBe(false);
    expect(sessionStorage.getItem("skillhub.admin.key")).toBeNull();
  });

  it("locks an open console when a refresh returns 403", async () => {
    const spies = mockAdminLoad();
    spies.overview.mockResolvedValueOnce(emptyOverview).mockRejectedValueOnce(new ApiError("Invalid admin console key.", 403));
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
    overview: vi.spyOn(paginationApi, "overview").mockResolvedValue(emptyOverview),
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
    systemCommands: vi.spyOn(api, "adminListSystemCommands").mockResolvedValue({ commands: [] }),
    expressionFunctions: vi.spyOn(api, "adminListExpressionFunctions").mockResolvedValue([]),
  };
}
