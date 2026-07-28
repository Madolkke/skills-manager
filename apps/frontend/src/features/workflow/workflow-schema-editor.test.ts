// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import { nextTick } from "vue";
import WorkflowJsonValueModal from "./components/WorkflowJsonValueModal.vue";
import WorkflowSchemaEditorModal from "./components/WorkflowSchemaEditorModal.vue";
import { workflowSchemasAssignable } from "./workflowJsonSchema";

afterEach(() => { document.body.innerHTML = ""; });

describe("Workflow Schema editor", () => {
  it("递归展示对象数组并按 Key 规范化确认结果", async () => {
    const wrapper = mount(WorkflowSchemaEditorModal, {
      attachTo: document.body,
      props: {
        open: true,
        fieldKey: "rows",
        readonly: false,
        schema: {
          type: "array", title: "数据行", description: "表格数据",
          items: {
            type: "object", title: "行", description: "", additionalProperties: false,
            required: ["status", "name"],
            properties: {
              status: { type: "string", title: "状态", description: "" },
              name: { type: "string", title: "名称", description: "" },
            },
          },
        },
      },
    });

    expect(document.body.textContent).toContain("数组元素");
    expect(document.body.textContent).toContain("对象属性");
    await clickButton("JSON Schema 预览");
    expect(document.body.querySelector("pre")?.textContent).toContain('"additionalProperties": false');
    await clickButton("确认 Schema");

    const confirmed = wrapper.emitted("confirm")?.[0]?.[0] as { items: { properties: Record<string, unknown>; required: string[] } };
    expect(Object.keys(confirmed.items.properties)).toEqual(["name", "status"]);
    expect(confirmed.items.required).toEqual(["name", "status"]);
  });

  it("关闭未保存弹窗时直接丢弃且不触发确认", async () => {
    const wrapper = mount(WorkflowSchemaEditorModal, {
      attachTo: document.body,
      props: { open: true, fieldKey: "value", readonly: false, schema: { type: "string", title: "值", description: "" } },
    });

    document.body.querySelector<HTMLButtonElement>('button[aria-label="关闭"]')!.click();
    await nextTick();
    expect(wrapper.emitted("close")).toHaveLength(1);
    expect(wrapper.emitted("confirm")).toBeUndefined();
  });

  it("拒绝重复的对象属性 Key 并恢复原值", async () => {
    mount(WorkflowSchemaEditorModal, {
      attachTo: document.body,
      props: {
        open: true,
        fieldKey: "row",
        readonly: false,
        schema: {
          type: "object", title: "行", description: "", additionalProperties: false,
          required: ["name", "status"],
          properties: {
            name: { type: "string", title: "名称", description: "" },
            status: { type: "string", title: "状态", description: "" },
          },
        },
      },
    });

    const propertyKeys = [...document.body.querySelectorAll<HTMLInputElement>(".workflow-schema-property-head label:first-child input")];
    propertyKeys[1]!.value = "name";
    propertyKeys[1]!.dispatchEvent(new Event("change"));
    await nextTick();

    expect(propertyKeys[1]!.value).toBe("status");
    await clickButton("JSON Schema 预览");
    expect(document.body.querySelector("pre")?.textContent).toContain('"status"');
  });

  it("JSON 固定值不匹配时警告但允许确认", async () => {
    const wrapper = mount(WorkflowJsonValueModal, {
      attachTo: document.body,
      props: {
        open: true, value: { count: "2" }, fieldName: "统计", readonly: false,
        schema: { type: "object", title: "统计", description: "", properties: { count: { type: "integer", title: "数量", description: "" } }, required: ["count"], additionalProperties: false },
      },
    });

    expect(document.body.textContent).toContain("与字段 Schema 不匹配");
    await clickButton("确认固定值");
    expect(wrapper.emitted("confirm")?.[0]).toEqual([{ count: "2" }]);
  });

  it("递归兼容规则允许 integer 赋给 number", () => {
    expect(workflowSchemasAssignable(
      { type: "array", title: "", description: "", items: { type: "integer", title: "", description: "" } },
      { type: "array", title: "", description: "", items: { type: "number", title: "", description: "" } },
    )).toBe(true);
  });
});

async function clickButton(label: string): Promise<void> {
  const button = [...document.body.querySelectorAll<HTMLButtonElement>("button")].find((item) => item.textContent?.includes(label));
  if (!button) throw new Error(`Button not found: ${label}`);
  button.click();
  await nextTick();
}
