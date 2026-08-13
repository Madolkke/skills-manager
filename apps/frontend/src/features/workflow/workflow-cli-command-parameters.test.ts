// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { CollectionDefinition } from "../../types";
import WorkflowCollectionFields from "./components/WorkflowCollectionFields.vue";
import { parseCliCommandParameters } from "./domain/cliCommandParameters";

describe("CLI 命令参数", () => {
  it("解析唯一的 Python 标识符并拒绝无效尖括号", () => {
    expect(parseCliCommandParameters("show <接口名> <peer_ip> <_private> <peer_ip>")).toEqual({ names: ["接口名", "peer_ip", "_private"] });
    expect(parseCliCommandParameters("show <peer-ip>").error).toBeTruthy();
    expect(parseCliCommandParameters("show <peer").error).toBeTruthy();
  });

  it("修改命令时创建、标记并删除同名输入和样例值", async () => {
    const wrapper = mount(WorkflowCollectionFields, { props: { definition: definition(), readonly: false } });
    const command = wrapper.get(".workflow-command-input");

    await command.setValue("display interface <slot_id> <slot_id>");
    const added = wrapper.emitted("change")?.at(-1)?.[0] as CollectionDefinition;
    expect(added.spec).toMatchObject({ commandParameterSyntax: "angle-v1" });
    expect(added.inputs).toHaveLength(1);
    expect(added.inputs[0]).toMatchObject({ key: "slot_id", required: true, schema: { type: "string", title: "slot_id" } });

    await wrapper.setProps({ definition: added });
    expect(wrapper.get(".workflow-command-parameter-badge").text()).toBe("命令参数");
    await wrapper.get(".workflow-command-input").setValue("display interface");
    const removed = wrapper.emitted("change")?.at(-1)?.[0] as CollectionDefinition;
    expect(removed.inputs).toEqual([]);
    expect((removed.spec as { outputSamples: Array<{ inputValues: Record<string, unknown> }> }).outputSamples[0].inputValues).toEqual({});
  });

  it("暂态非法命令保留既有输入", async () => {
    const current = definition();
    current.spec = { collectionType: "cli", commandTemplate: "display <slot_id>", outputSamples: [], commandParameterSyntax: "angle-v1" };
    current.inputs = [{ id: "input-slot", key: "slot_id", required: true, schema: { type: "string", title: "槽位", description: "" } }];
    const wrapper = mount(WorkflowCollectionFields, { props: { definition: current, readonly: false } });

    await wrapper.get(".workflow-command-input").setValue("display <slot_id");
    const changed = wrapper.emitted("change")?.at(-1)?.[0] as CollectionDefinition;
    expect(changed.inputs).toEqual(current.inputs);

    await wrapper.setProps({ definition: changed });
    await wrapper.get(".workflow-command-input").setValue("display interface");
    const recovered = wrapper.emitted("change")?.at(-1)?.[0] as CollectionDefinition;
    expect(recovered.inputs).toEqual([]);
  });
});

function definition(): CollectionDefinition {
  return {
    id: "collection-status", revision: 1, key: "status",
    metadata: { name: "状态", description: "", industry: "", device: "", versions: [], tags: [] },
    spec: { collectionType: "cli", commandTemplate: "display interface", outputSamples: [{ id: "sample-1", name: "示例", stdout: "", inputValues: { slot_id: "1" } }] },
    inputs: [], outputs: [],
  };
}
