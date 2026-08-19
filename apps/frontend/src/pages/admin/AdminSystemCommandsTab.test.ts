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

  it("以独立卡片编辑回显示例并提交结构化数据", async () => {
    const wrapper = mount(AdminSystemCommandsTab, {
      props: {
        commands: [{ ...command("status"), samples: [{ id: "sample-1", name: "正常", command: "show status", stdout: "ok" }] }],
        selectedCommandId: "status",
      },
    });

    expect(wrapper.findAll(".admin-command-sample")).toHaveLength(1);
    await wrapper.get("button[aria-label='添加回显示例']").trigger("click");
    expect(wrapper.findAll(".admin-command-sample")).toHaveLength(2);
    const cards = wrapper.findAll(".admin-command-sample");
    await cards[1]!.find("input").setValue("带参数");
    await cards[1]!.findAll("input")[1]!.setValue("show status detail");
    await cards[1]!.find("textarea").setValue("detail");
    await cards[0]!.get("button[aria-label='删除回显示例']").trigger("click");
    await wrapper.get(".admin-command-editor-foot button.is-primary").trigger("click");

    const payload = wrapper.emitted("update")?.[0]?.[1] as Record<string, unknown>;
    expect(payload.samples).toEqual([{ id: expect.any(String), name: "带参数", command: "show status detail", stdout: "detail" }]);
  });

  it("同步结构化 Schema 与 JSON，并阻止非法 JSON 保存", async () => {
    const wrapper = mount(AdminSystemCommandsTab, { props: { commands: [], selectedCommandId: "" } });
    await wrapper.get("input[placeholder='show_system_status']").setValue("show_status");
    await wrapper.get("input[placeholder='系统状态']").setValue("系统状态");
    await wrapper.get("input[placeholder='show interface <interface>']").setValue("show status");
    const json = wrapper.get("textarea.admin-command-json");
    await json.setValue(JSON.stringify({ type: "object", properties: { status: { type: "string" } }, required: ["status"], additionalProperties: false }));
    expect((wrapper.find(".workflow-schema-property input").element as HTMLInputElement).value).toBe("status");
    expect(wrapper.get(".admin-command-schema-pane:first-child").text()).toContain("对象属性");

    await json.setValue("{ invalid");
    expect(wrapper.text()).toContain("输出 Schema JSON 格式不正确");
    expect(wrapper.get(".admin-command-editor-foot button.is-primary").attributes("disabled")).toBeDefined();
  });

  it("TTP 和 stdout 使用等宽编辑框", () => {
    const wrapper = mount(AdminSystemCommandsTab, { props: { commands: [], selectedCommandId: "" } });
    expect(wrapper.get("textarea.admin-command-ttp").classes()).toContain("admin-command-mono");
    expect(wrapper.get("textarea[placeholder='可粘贴 TTP、厂商文档片段或审阅备注。']").classes()).toContain("admin-command-mono");
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
