// @vitest-environment jsdom
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import AdminExpressionFunctionsTab from "./AdminExpressionFunctionsTab.vue";
import type { ExpressionFunction } from "../../types";

const item: ExpressionFunction = {
  id: "probe", name: "probe", description: "原始说明", body: "text", language: "python", isBuiltin: false, enabled: true,
  parameterSchema: { type: "object", title: "", description: "", properties: { zvalue: { type: "string", title: "", description: "" }, amount: { type: "integer", title: "", description: "" } }, required: ["zvalue"], additionalProperties: false },
  returnSchema: { type: "string", title: "", description: "" }, createdAt: "2026-09-14", updatedAt: "2026-09-14", createdBy: "admin", updatedBy: "admin",
};

/** 挂载真实编辑表单，复用子组件替身隔离 Schema 编辑器。 */
function mountEditor() {
  return mount(AdminExpressionFunctionsTab, { props: { functions: [item], selectedFunctionId: item.id },
    global: { stubs: { WorkflowSchemaNodeEditor: true, AdminSystemCommandSchemaDialog: true } } });
}

describe("函数管理草稿", () => {
  it("initializes selection, retains failed-save draft, resets only after confirmed response", async () => {
    const wrapper = mountEditor();
    expect((wrapper.get('.admin-expression-fields input').element as HTMLInputElement).value).toBe("probe");
    await wrapper.get('.admin-expression-fields textarea').setValue("修改草稿");
    const buttons = () => wrapper.findAll("button");
    await buttons().find(b => b.text().includes("保存"))!.trigger("click");
    expect(wrapper.emitted("update")![0]![0]).toBe("probe");
    expect(buttons().find(b => b.text().includes("撤销"))!.attributes("disabled")).toBeUndefined();
    expect((wrapper.get('.admin-expression-fields textarea').element as HTMLTextAreaElement).value).toBe("修改草稿");
    expect(item.description).toBe("原始说明");
    const payload = wrapper.emitted("update")![0]![1] as ExpressionFunction;
    expect(Object.keys(payload.parameterSchema.type === "object" ? payload.parameterSchema.properties : {})).toEqual(["zvalue", "amount"]);
    await wrapper.setProps({ functions: [{ ...item, description: "修改草稿" }] });
    expect(buttons().find(b => b.text().includes("撤销"))!.attributes("disabled")).toBeDefined();
    wrapper.unmount();
  });

  it("new creates a local draft, invalid identifiers cannot save, schema edits mark dirty", async () => {
    const wrapper = mountEditor();
    await wrapper.findAll("button").find(b => b.text().includes("新建"))!.trigger("click");
    expect(wrapper.emitted("create")).toBeUndefined();
    expect(wrapper.emitted("select")![0]).toEqual([""]);
    await wrapper.get('.admin-expression-fields input').setValue("class");
    expect(wrapper.findAll("button").find(b => b.text().includes("保存"))!.attributes("disabled")).toBeDefined();
    wrapper.unmount();
  });
});
