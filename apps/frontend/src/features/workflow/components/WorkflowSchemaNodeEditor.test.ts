// @vitest-environment jsdom
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { WorkflowJsonSchema } from "../../../types";
import WorkflowSchemaNodeEditor from "./WorkflowSchemaNodeEditor.vue";

/** 用不同层级的必填状态验证编辑结果，避免误读父属性状态。 */
function schema(): WorkflowJsonSchema {
  return { type: "object", title: "", description: "", properties: {
    optional: { type: "string", title: "", description: "" },
    rows: { type: "array", title: "", description: "", items: {
      type: "object", title: "", description: "", properties: {
        name: { type: "string", title: "", description: "" },
      }, required: ["name"], additionalProperties: false,
    } },
  }, required: ["rows"], additionalProperties: false };
}

describe("Schema 属性必填编辑", () => {
  it("shows each property's state and updates nested array items", async () => {
    const wrapper = mount(WorkflowSchemaNodeEditor, { props: { schema: schema(), readonly: false, showRequired: true, showMetadata: false } });
    const boxes = wrapper.findAll('input[type="checkbox"]');
    expect(boxes.map(box => (box.element as HTMLInputElement).checked)).toEqual([false, true, true]);
    await boxes[2]!.setValue(false);
    const updated = wrapper.emitted("change")![0]![0] as WorkflowJsonSchema;
    expect(updated.type).toBe("object");
    if (updated.type !== "object") throw new Error("Expected object");
    const rows = updated.properties.rows!;
    if (rows.type !== "array" || rows.items.type !== "object") throw new Error("Expected object array");
    expect(rows.items.required).toEqual([]);
    expect(updated.required).toEqual(["rows"]);
    expect(wrapper.findAll('input[placeholder="字段名称"]')).toHaveLength(0);
    wrapper.unmount();
  });

  it("updates a root optional field and disables readonly controls", async () => {
    const wrapper = mount(WorkflowSchemaNodeEditor, { props: { schema: schema(), readonly: false, showRequired: true } });
    await wrapper.findAll('input[type="checkbox"]')[0]!.setValue(true);
    expect((wrapper.emitted("change")![0]![0] as { required: string[] }).required).toEqual(["rows", "optional"]);
    await wrapper.setProps({ readonly: true });
    expect(wrapper.findAll('input[type="checkbox"]').every(box => box.attributes("disabled") !== undefined)).toBe(true);
    wrapper.unmount();
  });
});
