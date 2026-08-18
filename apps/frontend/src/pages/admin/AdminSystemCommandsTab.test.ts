// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SystemCommand } from "../../types";
import AdminSystemCommandsTab from "./AdminSystemCommandsTab.vue";

describe("AdminSystemCommandsTab", () => {
  afterEach(() => vi.restoreAllMocks());

  it("支持搜索和启用状态筛选", async () => {
    const wrapper = mount(AdminSystemCommandsTab, {
      props: { commands: [command("status", true), command("version", false)], selectedCommandId: "status" },
    });

    expect(wrapper.findAll(".admin-directory-item")).toHaveLength(2);
    await wrapper.get("input[type='search']").setValue("version");
    expect(wrapper.findAll(".admin-directory-item")).toHaveLength(1);
    expect(wrapper.find(".admin-directory-item strong").text()).toBe("version");

    await wrapper.get("input[type='search']").setValue("");
    await wrapper.findAll("[role='tab']")[2]!.trigger("click");
    expect(wrapper.findAll(".admin-directory-item")).toHaveLength(1);
    expect(wrapper.find(".admin-directory-item i").text()).toBe("停用");
  });

  it("创建前即时提示必填字段并提交结构化 JSON", async () => {
    const wrapper = mount(AdminSystemCommandsTab, { props: { commands: [], selectedCommandId: "" } });
    expect(wrapper.text()).toContain("Key 不能为空");

    await wrapper.get("input[placeholder='show_system_status']").setValue("show_status");
    await wrapper.get("input[placeholder='系统状态']").setValue("系统状态");
    await wrapper.get("input[placeholder='show interface <interface>']").setValue("show status");
    await wrapper.get(".admin-command-editor-foot button.is-primary").trigger("click");

    const payload = wrapper.emitted("create")?.[0]?.[0] as Record<string, unknown>;
    expect(payload.key).toBe("show_status");
    expect(payload.expression).toBe("show status");
    expect(payload.outputSchema).toEqual(expect.objectContaining({ type: "object" }));
    expect(payload.samples).toEqual([]);
  });

  it("切换命令前保护未保存修改", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const wrapper = mount(AdminSystemCommandsTab, {
      props: { commands: [command("status"), command("version")], selectedCommandId: "status" },
    });
    await wrapper.get("input[placeholder='show_system_status']").setValue("changed");
    await wrapper.findAll(".admin-directory-item")[1]!.trigger("click");
    expect(wrapper.emitted("select")).toBeUndefined();
  });
});

function command(key: string, enabled = true): SystemCommand {
  return {
    id: key,
    source: "system",
    key,
    name: key,
    description: "",
    expression: `show ${key}`,
    metadata: { name: key, description: "", device: "", industry: "", versions: [], tags: [] },
    samples: [],
    outputSchema: { type: "object", properties: {}, required: [], additionalProperties: false },
    ttp: "",
    enabled,
  };
}
