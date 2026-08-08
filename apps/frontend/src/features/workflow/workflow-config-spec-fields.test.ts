// @vitest-environment jsdom

import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import type { CollectionDefinition, WorkflowConfigCommand, WorkflowValidationIssue } from "../../types";
import WorkflowConfigSpecFields from "./components/WorkflowConfigSpecFields.vue";

describe("WorkflowConfigSpecFields", () => {
  it("uses stable editor identities when root commands are reordered", async () => {
    const wrapper = mount(WorkflowConfigSpecFields, {
      props: { definition: configDefinition([command("first"), command("second")]), readonly: false },
    });

    const editors = wrapper.findAllComponents({ name: "WorkflowConfigCommandEditor" });
    const first = editors[0]!;
    const second = editors[1]!;
    await first.vm.$emit("move", [0], 1);

    const change = wrapper.emitted("change")?.at(-1)?.[0] as { config: { commands: Array<{ name: string }> } };
    expect(change.config.commands.map((item) => item.name)).toEqual(["second", "first"]);
    await wrapper.setProps({ definition: configDefinition([command("second"), command("first")]) });
    const reordered = wrapper.findAllComponents({ name: "WorkflowConfigCommandEditor" });
    expect(reordered[0]!.element).toBe(second.element);
    expect(reordered[1]!.element).toBe(first.element);
  });

  it("marks only the recursive command identified by its full schema path", () => {
    const issues: WorkflowValidationIssue[] = [{
      id: "issue-child", code: "CONFIG_COMMAND_PATTERN_INVALID", severity: "error", message: "子命令模式无效",
      selection: { type: "collection", id: "collection-config", revision: 1, itemId: "shared", field: "spec.config.commands[0].children[0].pattern" },
    }];
    const definition = configDefinition([
      { ...command("parent"), children: [command("shared")] },
      command("shared"),
    ]);
    const wrapper = mount(WorkflowConfigSpecFields, { props: { definition, readonly: false, issues } });
    const patternInputs = wrapper.findAll('input.workflow-monospace');

    expect(patternInputs.map((item) => item.attributes("aria-invalid"))).toEqual(["false", "true", "false"]);
  });

  it("disables recursive controls in readonly mode", () => {
    const wrapper = mount(WorkflowConfigSpecFields, {
      props: { definition: configDefinition([{ ...command("parent"), children: [command("child")] }]), readonly: true },
    });

    expect(wrapper.findAll("input, select, button").every((item) => item.attributes("disabled") !== undefined)).toBe(true);
  });
});

function configDefinition(commands: WorkflowConfigCommand[]): CollectionDefinition {
  return {
    id: "collection-config", revision: 1, key: "config", metadata: { name: "配置", description: "", industry: "", device: "", versions: [], tags: [] },
    spec: { collectionType: "config", config: { commands } }, inputs: [], outputs: [],
  };
}

function command(name: string) {
  return { name, unique: true, pattern: `display ${name}`, captures: {}, children: [] };
}
